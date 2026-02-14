import base64
import json

from datetime import datetime, timedelta

import redis.asyncio as redis

from cryptography.fernet import Fernet

from ..config import settings
from ..models import TokenInfo


class TokenManager:
    def __init__(self):
        key = settings.ENCRYPTION_KEY.encode() if isinstance(settings.ENCRYPTION_KEY, str) else settings.ENCRYPTION_KEY
        self.cipher_suite = Fernet(key)
        self.redis_client = None

    async def initialize(self):
        """Initialize Redis connection"""
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=False)

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

    def _encrypt_token(self, token: str) -> str:
        """Encrypt a token for storage"""
        token_bytes = token.encode('utf-8')
        encrypted_bytes = self.cipher_suite.encrypt(token_bytes)
        return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token"""
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode('utf-8'))
        decrypted_bytes = self.cipher_suite.decrypt(encrypted_bytes)
        return decrypted_bytes.decode('utf-8')

    async def store_access_token(self, session_id: str, token_info: TokenInfo):
        """Store access token in Redis with TTL"""
        if not self.redis_client:
            await self.initialize()

        key = f"access_token:{session_id}"
        value = {
            "access_token": token_info.access_token,
            "expires_in": token_info.expires_in,
            "created_at": token_info.created_at.isoformat(),
            "token_type": token_info.token_type,
            "scope": token_info.scope
        }

        await self.redis_client.setex(
            key,
            settings.ACCESS_TOKEN_TTL,
            json.dumps(value).encode('utf-8')
        )

    async def get_access_token(self, session_id: str) -> str | None:
        """Get access token from Redis"""
        if not self.redis_client:
            await self.initialize()

        key = f"access_token:{session_id}"
        token_data = await self.redis_client.get(key)

        if token_data:
            try:
                token_info = json.loads(token_data.decode('utf-8'))
                return token_info["access_token"]
            except (json.JSONDecodeError, KeyError):
                return None

        return None

    async def store_refresh_token(self, session_id: str, token_info: TokenInfo):
        """Store encrypted refresh token in Redis with TTL"""
        if not self.redis_client:
            await self.initialize()

        key = f"refresh_token:{session_id}"
        encrypted_token = self._encrypt_token(token_info.refresh_token)

        value = {
            "refresh_token": encrypted_token,
            "refresh_expires_in": token_info.refresh_expires_in,
            "created_at": token_info.created_at.isoformat()
        }

        await self.redis_client.setex(
            key,
            settings.REFRESH_TOKEN_TTL,
            json.dumps(value).encode('utf-8')
        )

    async def get_refresh_token(self, session_id: str) -> str | None:
        """Get and decrypt refresh token from Redis"""
        if not self.redis_client:
            await self.initialize()

        key = f"refresh_token:{session_id}"
        token_data = await self.redis_client.get(key)

        if token_data:
            try:
                token_info = json.loads(token_data.decode('utf-8'))
                encrypted_token = token_info["refresh_token"]
                return self._decrypt_token(encrypted_token)
            except (json.JSONDecodeError, KeyError):
                return None

        return None

    async def update_tokens(self, session_id: str, token_info: TokenInfo):
        """Update both access and refresh tokens"""
        await self.store_access_token(session_id, token_info)
        await self.store_refresh_token(session_id, token_info)

    async def delete_tokens(self, session_id: str):
        """Delete both access and refresh tokens for a session"""
        if not self.redis_client:
            await self.initialize()

        access_key = f"access_token:{session_id}"
        refresh_key = f"refresh_token:{session_id}"

        await self.redis_client.delete(access_key, refresh_key)

    async def is_access_token_expired(self, session_id: str) -> bool:
        """Check if access token is expired"""
        if not self.redis_client:
            await self.initialize()

        key = f"access_token:{session_id}"
        token_data = await self.redis_client.get(key)

        if not token_data:
            return True

        try:
            token_info = json.loads(token_data.decode('utf-8'))
            created_at = datetime.fromisoformat(token_info["created_at"])
            expires_in = token_info["expires_in"]

            expiry_time = created_at + timedelta(seconds=expires_in)
            return datetime.utcnow() > expiry_time
        except (json.JSONDecodeError, KeyError, ValueError):
            return True

    async def is_refresh_token_expired(self, session_id: str) -> bool:
        """Check if refresh token is expired"""
        if not self.redis_client:
            await self.initialize()

        key = f"refresh_token:{session_id}"
        token_data = await self.redis_client.get(key)

        if not token_data:
            return True

        try:
            token_info = json.loads(token_data.decode('utf-8'))
            created_at = datetime.fromisoformat(token_info["created_at"])
            refresh_expires_in = token_info["refresh_expires_in"]

            expiry_time = created_at + timedelta(seconds=refresh_expires_in)
            return datetime.utcnow() > expiry_time
        except (json.JSONDecodeError, KeyError, ValueError):
            return True


# Global instance
token_manager = TokenManager()
