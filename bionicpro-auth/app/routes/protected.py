from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth.keycloak import keycloak_client
from ..middleware.session_rotation import get_current_session
from ..models import ProtectedResourceResponse, SessionData, UserInfo

router = APIRouter(prefix="/api", tags=["protected"])


def require_auth(request: Request) -> SessionData:
    """Dependency to require authentication"""
    session = get_current_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")
    return session


@router.get("/protected", response_model=ProtectedResourceResponse)
async def protected_endpoint(
    request: Request,
    session: SessionData = Depends(require_auth)
):
    """Example protected endpoint"""
    user_info = UserInfo(**session.user_info)

    return ProtectedResourceResponse(
        success=True,
        message="This is a protected resource",
        user_info=user_info,
        data={
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat()
        }
    )


@router.get("/user/profile", response_model=ProtectedResourceResponse)
async def get_user_profile(
    request: Request,
    session: SessionData = Depends(require_auth)
):
    """Get user profile information"""
    user_info = UserInfo(**session.user_info)

    return ProtectedResourceResponse(
        success=True,
        message="User profile retrieved",
        user_info=user_info,
        data={
            "profile": {
                "user_id": session.user_id,
                "email": user_info.email,
                "name": user_info.name,
                "preferred_username": user_info.preferred_username,
                "roles": user_info.roles
            }
        }
    )


@router.get("/user/sessions", response_model=ProtectedResourceResponse)
async def get_user_sessions(
    request: Request,
    session: SessionData = Depends(require_auth)
):
    """Get all active sessions for the current user"""
    from ..auth.session import session_manager

    user_sessions = await session_manager.get_user_sessions(session.user_id)

    sessions_data = []
    for user_session in user_sessions:
        sessions_data.append({
            "session_id": user_session.session_id,
            "created_at": user_session.created_at.isoformat(),
            "last_accessed": user_session.last_accessed.isoformat(),
            "expires_at": user_session.expires_at.isoformat(),
            "is_current": user_session.session_id == session.session_id
        })

    return ProtectedResourceResponse(
        success=True,
        message="User sessions retrieved",
        user_info=UserInfo(**session.user_info),
        data={
            "sessions": sessions_data,
            "total_sessions": len(sessions_data)
        }
    )


@router.post("/user/sessions/revoke", response_model=ProtectedResourceResponse)
async def revoke_user_sessions(
    request: Request,
    session: SessionData = Depends(require_auth),
    session_id: str | None = None
):
    """Revoke a specific session or all sessions except current"""
    from ..auth.session import session_manager

    if session_id:
        # Revoke specific session
        if session_id == session.session_id:
            raise HTTPException(status_code=400, detail="Cannot revoke current session through this endpoint")

        target_session = await session_manager.get_session(session_id)
        if not target_session or target_session.user_id != session.user_id:
            raise HTTPException(status_code=404, detail="Session not found")

        await session_manager.delete_session(session_id)
        from ..auth.tokens import token_manager
        await token_manager.delete_tokens(session_id)

        message = f"Session {session_id} revoked"
    else:
        # Revoke all sessions except current
        user_sessions = await session_manager.get_user_sessions(session.user_id)
        revoked_count = 0

        for user_session in user_sessions:
            if user_session.session_id != session.session_id:
                await session_manager.delete_session(user_session.session_id)
                from ..auth.tokens import token_manager
                await token_manager.delete_tokens(user_session.session_id)
                revoked_count += 1

        message = f"Revoked {revoked_count} sessions"

    return ProtectedResourceResponse(
        success=True,
        message=message,
        user_info=UserInfo(**session.user_info),
        data={"revoked": True}
    )


@router.get("/token/info", response_model=ProtectedResourceResponse)
async def get_token_info(
    request: Request,
    session: SessionData = Depends(require_auth)
):
    """Get information about current tokens"""
    from ..auth.tokens import token_manager

    session_id = session.session_id

    # Get token status
    access_token_expired = await token_manager.is_access_token_expired(session_id)
    refresh_token_expired = await token_manager.is_refresh_token_expired(session_id)

    # Get access token (without exposing it)
    access_token = await token_manager.get_access_token(session_id)
    has_access_token = bool(access_token)

    # Get refresh token status (without exposing it)
    refresh_token = await token_manager.get_refresh_token(session_id)
    has_refresh_token = bool(refresh_token)

    return ProtectedResourceResponse(
        success=True,
        message="Token information retrieved",
        user_info=UserInfo(**session.user_info),
        data={
            "has_access_token": has_access_token,
            "access_token_expired": access_token_expired,
            "has_refresh_token": has_refresh_token,
            "refresh_token_expired": refresh_token_expired,
            "session_valid": not session.is_expired()
        }
    )


@router.post("/token/refresh", response_model=ProtectedResourceResponse)
async def manual_token_refresh(
    request: Request,
    session: SessionData = Depends(require_auth)
):
    """Manually refresh access token"""
    from ..auth.tokens import token_manager

    session_id = session.session_id

    try:
        # Get refresh token
        refresh_token = await token_manager.get_refresh_token(session_id)
        if not refresh_token:
            raise HTTPException(status_code=400, detail="No refresh token available")

        # Refresh access token
        new_token_info = await keycloak_client.refresh_access_token(refresh_token)

        # Update stored tokens
        await token_manager.update_tokens(session_id, new_token_info)

        # Update session
        from ..auth.session import session_manager
        await session_manager.update_session(session)

        return ProtectedResourceResponse(
            success=True,
            message="Token refreshed successfully",
            user_info=UserInfo(**session.user_info),
            data={
                "expires_in": new_token_info.expires_in,
                "refresh_expires_in": new_token_info.refresh_expires_in
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token refresh failed: {str(e)}")


@router.get("/health", response_model=ProtectedResourceResponse)
async def health_check():
    """Health check endpoint (no authentication required)"""
    return ProtectedResourceResponse(
        success=True,
        message="Service is healthy",
        data={
            "status": "healthy",
            "service": "bionicpro-auth",
            "version": "1.0.0"
        }
    )


@router.get("/debug/session", response_model=ProtectedResourceResponse)
async def debug_session(
    request: Request,
    session: SessionData = Depends(require_auth)
):
    """Debug endpoint to show session information (development only)"""
    user_info = UserInfo(**session.user_info)

    return ProtectedResourceResponse(
        success=True,
        message="Session debug information",
        user_info=user_info,
        data={
            "session": {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat(),
                "last_accessed": session.last_accessed.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "is_expired": session.is_expired()
            },
            "cookies": dict(request.cookies),
            "headers": dict(request.headers)
        }
    )
