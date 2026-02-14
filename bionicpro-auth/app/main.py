from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth.keycloak import keycloak_client
from .auth.session import session_manager
from .auth.tokens import token_manager
from .config import settings
from .middleware.session_rotation import AuthenticationMiddleware, SessionRotationMiddleware
from .routes import auth, protected
from .services.user_profile import user_profile_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    await token_manager.initialize()
    await session_manager.initialize()
    await user_profile_service.initialize()

    yield

    # Shutdown
    await keycloak_client.close()
    await token_manager.close()
    await session_manager.close()
    await user_profile_service.close()


# Create FastAPI application
app = FastAPI(
    title="BionicPro Auth Service",
    description="Backend for Frontend authentication service with secure token management",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add session rotation middleware
app.add_middleware(
    SessionRotationMiddleware,
    exclude_paths=[
        "/auth/login",
        "/auth/callback",
        "/health",
        "/docs",
        "/openapi.json",
        "/favicon.ico"
    ]
)

# Add authentication middleware for protected routes
app.add_middleware(
    AuthenticationMiddleware,
    protected_paths=[
        "/api/",
        "/auth/refresh",
        "/auth/logout",
        "/auth/me",
        "/auth/profile",
        "/auth/yandex/profile"
    ]
)

# Include routers
app.include_router(auth.router)
app.include_router(protected.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "BionicPro Auth Service",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "bionicpro-auth",
        "version": "1.0.0"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.APP_HOST == "0.0.0.0" else "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level="info"
    )
