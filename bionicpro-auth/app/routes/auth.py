import secrets

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..auth.keycloak import keycloak_client
from ..auth.session import session_manager
from ..auth.tokens import token_manager
from ..config import settings
from ..models import (
    AuthResponse,
    CallbackResponse,
    ConsentRequest,
    ConsentResponse,
    LoginResponse,
    PKCEChallenge,
    UserInfo,
)
from ..services.user_profile import user_profile_service

router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize templates for consent page
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_model=LoginResponse)
async def login(request: Request, redirect_uri: str | None = None):
    """Initiate login flow with PKCE"""
    # Generate PKCE challenge
    pkce_challenge = keycloak_client.generate_pkce_challenge()

    # Store PKCE challenge in session temporarily
    # In production, you might want to store this in Redis with TTL
    state = secrets.token_urlsafe(32)

    # Store PKCE challenge and state in temporary storage
    # For now, we'll use a simple approach - in production, use Redis
    temp_key = f"pkce:{state}"
    if not token_manager.redis_client:
        await token_manager.initialize()

    await token_manager.redis_client.setex(
        temp_key,
        600,  # 10 minutes TTL
        pkce_challenge.json().encode('utf-8')
    )

    # Determine redirect URI
    callback_uri = redirect_uri or f"{settings.APP_HOST}:{settings.APP_PORT}/auth/callback"
    if not callback_uri.startswith('http'):
        callback_uri = f"http://{callback_uri}"

    # Build authorization URL
    auth_url = keycloak_client.get_authorization_url(
        pkce_challenge=pkce_challenge,
        redirect_uri=callback_uri,
        state=state
    )

    return LoginResponse(
        redirect_url=auth_url,
        state=state
    )


@router.get("/callback", response_model=CallbackResponse)
async def callback(
    request: Request,
    response: Response,
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
    error_description: str | None = Query(None)
):
    """Handle OAuth callback from Keycloak"""

    # Check for errors
    if error:
        return CallbackResponse(
            success=False,
            message=f"Authentication failed: {error_description or error}"
        )

    try:
        # Retrieve PKCE challenge from temporary storage
        temp_key = f"pkce:{state}"
        if not token_manager.redis_client:
            await token_manager.initialize()

        pkce_data = await token_manager.redis_client.get(temp_key)
        if not pkce_data:
            return CallbackResponse(
                success=False,
                message="Invalid or expired state parameter"
            )

        # Clean up temporary storage
        await token_manager.redis_client.delete(temp_key)

        # Parse PKCE challenge
        import json
        pkce_dict = json.loads(pkce_data.decode('utf-8'))
        pkce_challenge = PKCEChallenge(**pkce_dict)

        # Check if PKCE challenge is expired
        if pkce_challenge.is_expired():
            return CallbackResponse(
                success=False,
                message="PKCE challenge expired"
            )

        # Exchange authorization code for tokens
        callback_uri = f"http://{settings.APP_HOST}:{settings.APP_PORT}/auth/callback"
        token_info = await keycloak_client.exchange_code_for_tokens(
            code=code,
            pkce_challenge=pkce_challenge,
            redirect_uri=callback_uri
        )

        # Get user information
        user_info = await keycloak_client.get_user_info(token_info.access_token)

        # Create session
        session = await session_manager.create_session(user_info)

        # Store tokens
        await token_manager.store_access_token(session.session_id, token_info)
        await token_manager.store_refresh_token(session.session_id, token_info)

        # Set session cookie
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=session.session_id,
            max_age=settings.SESSION_MAX_AGE,
            path="/",
            httponly=True,
            secure=True,
            samesite="strict"
        )

        return CallbackResponse(
            success=True,
            message="Authentication successful",
            user_info=user_info
        )

    except Exception as e:
        return CallbackResponse(
            success=False,
            message=f"Authentication failed: {str(e)}"
        )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(request: Request, response: Response):
    """Refresh access token"""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    # Validate session
    session = await session_manager.get_session(session_id)
    if not session or session.is_expired():
        raise HTTPException(status_code=401, detail="Session expired")

    try:
        # Get refresh token
        refresh_token = await token_manager.get_refresh_token(session_id)
        if not refresh_token:
            raise HTTPException(status_code=401, detail="No refresh token")

        # Refresh access token
        new_token_info = await keycloak_client.refresh_access_token(refresh_token)

        # Update stored tokens
        await token_manager.update_tokens(session_id, new_token_info)

        # Update session
        await session_manager.update_session(session)

        return AuthResponse(
            success=True,
            message="Token refreshed successfully",
            data={"expires_in": new_token_info.expires_in}
        )

    except Exception as e:
        # Token refresh failed, invalidate session
        await session_manager.delete_session(session_id)
        await token_manager.delete_tokens(session_id)

        response.delete_cookie(
            key=settings.SESSION_COOKIE_NAME,
            path="/",
            httponly=True,
            secure=True,
            samesite="strict"
        )

        raise HTTPException(status_code=401, detail=f"Token refresh failed: {str(e)}")


@router.post("/logout", response_model=AuthResponse)
async def logout(request: Request, response: Response):
    """Logout user and invalidate session"""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_id:
        return AuthResponse(
            success=True,
            message="Already logged out"
        )

    try:
        # Get refresh token for Keycloak logout
        refresh_token = await token_manager.get_refresh_token(session_id)

        # Logout from Keycloak
        if refresh_token:
            await keycloak_client.logout(refresh_token)

        # Delete local session and tokens
        await session_manager.delete_session(session_id)
        await token_manager.delete_tokens(session_id)

        # Clear session cookie
        response.delete_cookie(
            key=settings.SESSION_COOKIE_NAME,
            path="/",
            httponly=True,
            secure=True,
            samesite="strict"
        )

        return AuthResponse(
            success=True,
            message="Logout successful"
        )

    except Exception as e:
        return AuthResponse(
            success=False,
            message=f"Logout failed: {str(e)}"
        )


@router.get("/me", response_model=AuthResponse)
async def get_current_user(request: Request):
    """Get current user information"""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    # Validate session
    session = await session_manager.get_session(session_id)
    if not session or session.is_expired():
        raise HTTPException(status_code=401, detail="Session expired")

    # Get user info from session
    user_info = UserInfo(**session.user_info)

    return AuthResponse(
        success=True,
        message="User information retrieved",
        data={
            "user_id": session.user_id,
            "user_info": user_info.dict(),
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "expires_at": session.expires_at.isoformat()
        }
    )


@router.get("/yandex/profile", response_model=AuthResponse)
async def fetch_yandex_profile(
    request: Request,
    session_id: str = Cookie(None),
    consent: bool = Query(False),
    redirect_url: str | None = Query(None)
):
    """
    Fetch and store Yandex user profile after authentication.
    Requires user consent for data storage.
    """
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    # Validate session
    session = await session_manager.get_session(session_id)
    if not session or session.is_expired():
        raise HTTPException(status_code=401, detail="Session expired")

    try:
        # Get access token from stored tokens
        access_token = await token_manager.get_access_token(session_id)
        if not access_token:
            raise HTTPException(status_code=401, detail="No access token found")

        # Check if user came from Yandex identity provider
        user_info = UserInfo(**session.user_info)
        identity_provider = user_info.dict().get("identity_provider")

        if identity_provider != "yandex":
            return AuthResponse(
                success=False,
                message="This endpoint is only for Yandex ID users"
            )

        # Fetch Yandex profile
        yandex_profile = await user_profile_service.fetch_yandex_profile(access_token)

        if not consent:
            # Store consent request temporarily and show consent page
            consent_key = f"consent:{session_id}"
            if not token_manager.redis_client:
                await token_manager.initialize()

            consent_request = ConsentRequest(
                user_id=session.user_id,
                yandex_profile=yandex_profile,
                redirect_url=redirect_url
            )

            await token_manager.redis_client.setex(
                consent_key,
                600,  # 10 minutes TTL
                consent_request.json().encode('utf-8')
            )

            return AuthResponse(
                success=False,
                message="User consent required",
                data={
                    "consent_required": True,
                    "consent_url": f"/auth/yandex/consent?session_id={session_id}"
                }
            )

        # Process consent (user approved)
        consent_request = ConsentRequest(
            user_id=session.user_id,
            yandex_profile=yandex_profile,
            redirect_url=redirect_url
        )

        consent_response = await user_profile_service.process_consent(
            consent_request,
            consent_given=True
        )

        return AuthResponse(
            success=consent_response.success,
            message=consent_response.message,
            data={
                "profile_stored": consent_response.success,
                "user_profile": consent_response.user_profile.dict() if consent_response.user_profile else None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        return AuthResponse(
            success=False,
            message=f"Failed to fetch Yandex profile: {str(e)}"
        )


@router.get("/yandex/consent", response_class=HTMLResponse)
async def show_consent_page(request: Request, session_id: str = Query(...)):
    """Show consent page for Yandex profile data storage"""
    try:
        # Get consent request from temporary storage
        consent_key = f"consent:{session_id}"
        if not token_manager.redis_client:
            await token_manager.initialize()

        consent_data = await token_manager.redis_client.get(consent_key)
        if not consent_data:
            raise HTTPException(status_code=404, detail="Consent request not found or expired")

        import json
        consent_dict = json.loads(consent_data.decode('utf-8'))
        consent_request = ConsentRequest(**consent_dict)

        # Extract relevant profile data for display
        profile_data = consent_request.yandex_profile
        display_data = {
            "name": (
                profile_data.get("display_name") or
                f"{profile_data.get('first_name', '')} {profile_data.get('last_name', '')}".strip()
            ),
            "email": profile_data.get("default_email"),
            "username": profile_data.get("login"),
            "avatar_url": (
                f"https://avatars.yandex.net/get-yapic/{profile_data.get('default_avatar_id')}/islands-retina-50"
                if profile_data.get("default_avatar_id") and not profile_data.get("is_avatar_empty")
                else None
            )
        }

        return templates.TemplateResponse(
            "consent.html",
            {
                "request": request,
                "session_id": session_id,
                "profile_data": display_data,
                "redirect_url": consent_request.redirect_url or "/dashboard"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load consent page: {str(e)}")


@router.post("/yandex/consent", response_model=ConsentResponse)
async def process_consent(
    request: Request,
    session_id: str = Query(...),
    consent_given: bool = Query(...),
    redirect_url: str | None = Query(None)
):
    """Process user consent for Yandex profile data storage"""
    try:
        # Get consent request from temporary storage
        consent_key = f"consent:{session_id}"
        if not token_manager.redis_client:
            await token_manager.initialize()

        consent_data = await token_manager.redis_client.get(consent_key)
        if not consent_data:
            raise HTTPException(status_code=404, detail="Consent request not found or expired")

        # Clean up temporary storage
        await token_manager.redis_client.delete(consent_key)

        import json
        consent_dict = json.loads(consent_data.decode('utf-8'))
        consent_request = ConsentRequest(**consent_dict)

        # Update redirect URL if provided
        if redirect_url:
            consent_request.redirect_url = redirect_url

        # Process consent
        consent_response = await user_profile_service.process_consent(
            consent_request,
            consent_given
        )

        return consent_response

    except HTTPException:
        raise
    except Exception as e:
        return ConsentResponse(
            success=False,
            message=f"Error processing consent: {str(e)}"
        )


@router.get("/profile", response_model=AuthResponse)
async def get_user_profile(request: Request):
    """Get stored user profile data"""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    # Validate session
    session = await session_manager.get_session(session_id)
    if not session or session.is_expired():
        raise HTTPException(status_code=401, detail="Session expired")

    try:
        # Get user profile from database
        user_profile = await user_profile_service.get_user_profile(session.user_id)

        return AuthResponse(
            success=True,
            message="User profile retrieved successfully",
            data={
                "user_profile": user_profile.dict(),
                "has_consent": user_profile.consent_given,
                "consent_timestamp": user_profile.consent_timestamp
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        return AuthResponse(
            success=False,
            message=f"Failed to retrieve user profile: {str(e)}"
        )


@router.delete("/profile", response_model=AuthResponse)
async def delete_user_profile(request: Request):
    """Delete stored user profile data"""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    # Validate session
    session = await session_manager.get_session(session_id)
    if not session or session.is_expired():
        raise HTTPException(status_code=401, detail="Session expired")

    try:
        # Delete user profile from database
        deleted = await user_profile_service.delete_user_profile(session.user_id)

        return AuthResponse(
            success=deleted,
            message="User profile deleted successfully" if deleted else "No profile found to delete"
        )

    except Exception as e:
        return AuthResponse(
            success=False,
            message=f"Failed to delete user profile: {str(e)}"
        )


@router.get("/status", response_model=AuthResponse)
async def auth_status(request: Request):
    """Check authentication status"""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_id:
        return AuthResponse(
            success=False,
            message="Not authenticated",
            data={"authenticated": False}
        )

    # Validate session
    session = await session_manager.get_session(session_id)
    if not session or session.is_expired():
        return AuthResponse(
            success=False,
            message="Session expired",
            data={"authenticated": False}
        )

    # Check token status
    access_token_expired = await token_manager.is_access_token_expired(session_id)
    refresh_token_expired = await token_manager.is_refresh_token_expired(session_id)

    return AuthResponse(
        success=True,
        message="Authenticated",
        data={
            "authenticated": True,
            "session_id": session.session_id,
            "user_id": session.user_id,
            "access_token_expired": access_token_expired,
            "refresh_token_expired": refresh_token_expired,
            "session_expires_at": session.expires_at.isoformat()
        }
    )
