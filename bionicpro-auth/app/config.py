from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Keycloak Configuration
    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_REALM: str = "reports-realm"
    KEYCLOAK_CLIENT_ID: str = "reports-frontend"
    KEYCLOAK_CLIENT_SECRET: str | None = None

    # Redis Configuration
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0

    # Session Configuration
    SESSION_SECRET_KEY: str = "change-me-in-production"
    SESSION_MAX_AGE: int = 1800  # 30 minutes
    SESSION_COOKIE_NAME: str = "bionicpro_session"

    # Token Configuration
    ACCESS_TOKEN_TTL: int = 120  # 2 minutes
    REFRESH_TOKEN_TTL: int = 2592000  # 30 days
    ENCRYPTION_KEY: str = "change-me-in-production-32-bytes"

    # Application Configuration
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"

    # Security Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Yandex OAuth Configuration
    YANDEX_CLIENT_ID: str | None = None
    YANDEX_CLIENT_SECRET: str | None = None
    YANDEX_OAUTH_URL: str = "https://oauth.yandex.ru/authorize"
    YANDEX_TOKEN_URL: str = "https://oauth.yandex.ru/token"
    YANDEX_USERINFO_URL: str = "https://login.yandex.ru/info"

    # Database Configuration for User Profiles
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "bionicpro_users"
    POSTGRES_USER: str = "bionicpro"
    POSTGRES_PASSWORD: str = "secure_password"

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def keycloak_auth_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/auth"

    @property
    def keycloak_token_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/token"

    @property
    def keycloak_logout_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/logout"

    @property
    def keycloak_userinfo_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/userinfo"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
