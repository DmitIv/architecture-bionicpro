from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..auth.keycloak import keycloak_client
from ..auth.session import session_manager
from ..auth.tokens import token_manager
from ..config import settings
from ..models import SessionData


class SessionRotationMiddleware(BaseHTTPMiddleware):
    """Middleware for session rotation and automatic token refresh"""

    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/auth/login",
            "/auth/callback",
            "/health",
            "/docs",
            "/openapi.json"
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip session rotation for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Get session ID from cookie
        session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

        if not session_id:
            # No session, continue without authentication
            return await call_next(request)

        try:
            # Validate session
            session = await session_manager.get_session(session_id)
            if not session or session.is_expired():
                # Session expired or invalid, clear cookie and continue
                response = await call_next(request)
                response.delete_cookie(
                    key=settings.SESSION_COOKIE_NAME,
                    path="/",
                    httponly=True,
                    secure=True,
                    samesite="strict"
                )
                return response

            # Check if access token needs refresh
            access_token_expired = await token_manager.is_access_token_expired(session_id)

            if access_token_expired:
                # Try to refresh the access token
                refresh_token = await token_manager.get_refresh_token(session_id)
                if refresh_token:
                    try:
                        new_token_info = await keycloak_client.refresh_access_token(refresh_token)
                        await token_manager.update_tokens(session_id, new_token_info)
                    except Exception:
                        # Token refresh failed, invalidate session
                        await session_manager.delete_session(session_id)
                        await token_manager.delete_tokens(session_id)

                        response = await call_next(request)
                        response.delete_cookie(
                            key=settings.SESSION_COOKIE_NAME,
                            path="/",
                            httponly=True,
                            secure=True,
                            samesite="strict"
                        )
                        return response
                else:
                    # No refresh token available, invalidate session
                    await session_manager.delete_session(session_id)
                    await token_manager.delete_tokens(session_id)

                    response = await call_next(request)
                    response.delete_cookie(
                        key=settings.SESSION_COOKIE_NAME,
                        path="/",
                        httponly=True,
                        secure=True,
                        samesite="strict"
                    )
                    return response

            # Rotate session ID to prevent session fixation
            new_session = await session_manager.rotate_session(session_id)
            if new_session:
                # Migrate tokens to new session
                access_token = await token_manager.get_access_token(session_id)
                refresh_token = await token_manager.get_refresh_token(session_id)

                if access_token and refresh_token:
                    # Create token info for migration
                    from ..models import TokenInfo
                    token_info = TokenInfo(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_in=settings.ACCESS_TOKEN_TTL,
                        refresh_expires_in=settings.REFRESH_TOKEN_TTL
                    )

                    # Store tokens with new session ID
                    await token_manager.update_tokens(new_session.session_id, token_info)
                    # Delete old tokens
                    await token_manager.delete_tokens(session_id)

                # Update request state with new session
                request.state.session = new_session
                request.state.session_id = new_session.session_id

                # Continue with the request
                response = await call_next(request)

                # Set new session cookie
                response.set_cookie(
                    key=settings.SESSION_COOKIE_NAME,
                    value=new_session.session_id,
                    max_age=settings.SESSION_MAX_AGE,
                    path="/",
                    httponly=True,
                    secure=True,
                    samesite="strict"
                )

                return response
            else:
                # Session rotation failed, use original session
                request.state.session = session
                request.state.session_id = session_id
                return await call_next(request)

        except Exception:
            # Log error and continue without session rotation
            # In production, you might want to log this error
            return await call_next(request)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to require authentication for protected routes"""

    def __init__(self, app, protected_paths: list = None):
        super().__init__(app)
        self.protected_paths = protected_paths or [
            "/api/",
            "/protected/",
            "/auth/refresh",
            "/auth/logout"
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if path requires authentication
        path_protected = any(
            request.url.path.startswith(protected_path)
            for protected_path in self.protected_paths
        )

        if not path_protected:
            return await call_next(request)

        # Get session ID from cookie
        session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

        if not session_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )

        # Validate session
        session = await session_manager.get_session(session_id)
        if not session or session.is_expired():
            return JSONResponse(
                status_code=401,
                content={"detail": "Session expired"}
            )

        # Check if access token is valid
        access_token = await token_manager.get_access_token(session_id)
        if not access_token:
            return JSONResponse(
                status_code=401,
                content={"detail": "No access token"}
            )

        # Validate access token with Keycloak
        token_valid = await keycloak_client.validate_token(access_token)
        if not token_valid:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid access token"}
            )

        # Add session to request state
        request.state.session = session
        request.state.session_id = session_id
        request.state.access_token = access_token

        return await call_next(request)


def get_current_session(request: Request) -> SessionData | None:
    """Get current session from request state"""
    return getattr(request.state, 'session', None)


def get_current_user_id(request: Request) -> str | None:
    """Get current user ID from request state"""
    session = get_current_session(request)
    return session.user_id if session else None


def get_current_access_token(request: Request) -> str | None:
    """Get current access token from request state"""
    return getattr(request.state, 'access_token', None)
