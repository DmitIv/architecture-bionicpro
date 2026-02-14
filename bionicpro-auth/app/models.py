import uuid

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field


class SessionData(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_info: dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def update_last_accessed(self):
        self.last_accessed = datetime.utcnow()


class TokenInfo(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_expires_in: int
    scope: str
    id_token: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def is_access_token_expired(self) -> bool:
        expiry_time = self.created_at + timedelta(seconds=self.expires_in)
        return datetime.utcnow() > expiry_time

    def is_refresh_token_expired(self) -> bool:
        expiry_time = self.created_at + timedelta(seconds=self.refresh_expires_in)
        return datetime.utcnow() > expiry_time


class PKCEChallenge(BaseModel):
    code_verifier: str
    code_challenge: str
    challenge_method: str = "S256"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def is_expired(self, max_age_minutes: int = 10) -> bool:
        expiry_time = self.created_at + timedelta(minutes=max_age_minutes)
        return datetime.utcnow() > expiry_time


class UserInfo(BaseModel):
    sub: str  # Subject (user ID)
    email: str | None = None
    name: str | None = None
    preferred_username: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    email_verified: bool | None = None
    roles: list = Field(default_factory=list)

    @classmethod
    def from_keycloak_claims(cls, claims: dict[str, Any]) -> "UserInfo":
        return cls(
            sub=claims.get("sub"),
            email=claims.get("email"),
            name=claims.get("name"),
            preferred_username=claims.get("preferred_username"),
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
            email_verified=claims.get("email_verified"),
            roles=claims.get("roles", [])
        )


class AuthResponse(BaseModel):
    success: bool
    message: str
    data: dict[str, Any] | None = None


class LoginResponse(BaseModel):
    redirect_url: str
    state: str


class CallbackResponse(BaseModel):
    success: bool
    message: str
    user_info: UserInfo | None = None


class ProtectedResourceResponse(BaseModel):
    success: bool
    message: str
    user_info: UserInfo | None = None
    data: dict[str, Any] | None = None


class UserProfile(BaseModel):
    id: int | None = None
    user_id: str
    yandex_id: str | None = None
    username: str | None = None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    birthday: str | None = None  # ISO date string
    gender: str | None = None
    profile_data: dict[str, Any] | None = None
    consent_given: bool = False
    consent_timestamp: str | None = None  # ISO datetime string
    created_at: str | None = None  # ISO datetime string
    updated_at: str | None = None  # ISO datetime string

    @classmethod
    def from_yandex_profile(cls, user_id: str, yandex_data: dict[str, Any]) -> "UserProfile":
        """Create UserProfile from Yandex API response"""
        return cls(
            user_id=user_id,
            yandex_id=yandex_data.get("id"),
            username=yandex_data.get("login"),
            email=yandex_data.get("default_email"),
            first_name=yandex_data.get("first_name"),
            last_name=yandex_data.get("last_name"),
            display_name=yandex_data.get("display_name"),
            avatar_url=(
                f"https://avatars.yandex.net/get-yapic/{yandex_data.get('default_avatar_id')}/islands-retina-50"
                if yandex_data.get("default_avatar_id") and not yandex_data.get("is_avatar_empty")
                else None
            ),
            phone=yandex_data.get("default_phone"),
            birthday=yandex_data.get("birthday"),
            gender=yandex_data.get("sex"),
            profile_data=yandex_data
        )


class ConsentRequest(BaseModel):
    user_id: str
    yandex_profile: dict[str, Any]
    redirect_url: str | None = None


class ConsentResponse(BaseModel):
    success: bool
    message: str
    user_profile: UserProfile | None = None
    redirect_url: str | None = None
