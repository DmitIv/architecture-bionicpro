import json
import uuid

from datetime import datetime, timedelta

import redis.asyncio as redis

from ..config import settings
from ..models import SessionData, UserInfo


class SessionManager:
    def __init__(self):
        self.redis_client = None

    async def initialize(self):
        """Initialize Redis connection"""
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=False)

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

    async def create_session(self, user_info: UserInfo) -> SessionData:
        """Create a new session"""
        if not self.redis_client:
            await self.initialize()

        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(seconds=settings.SESSION_MAX_AGE)

        session_data = SessionData(
            session_id=session_id,
            user_id=user_info.sub,
            user_info=user_info.dict(),
            expires_at=expires_at
        )

        key = f"session:{session_id}"
        value = session_data.json()

        await self.redis_client.setex(
            key,
            settings.SESSION_MAX_AGE,
            value.encode('utf-8')
        )

        return session_data

    async def get_session(self, session_id: str) -> SessionData | None:
        """Get session data by session ID"""
        if not self.redis_client:
            await self.initialize()

        key = f"session:{session_id}"
        session_data = await self.redis_client.get(key)

        if session_data:
            try:
                session_json = session_data.decode('utf-8')
                session_dict = json.loads(session_json)
                return SessionData(**session_dict)
            except (json.JSONDecodeError, ValueError):
                return None

        return None

    async def update_session(self, session_data: SessionData):
        """Update session data"""
        if not self.redis_client:
            await self.initialize()

        session_data.update_last_accessed()

        key = f"session:{session_data.session_id}"
        value = session_data.json()

        # Calculate remaining TTL
        remaining_ttl = int((session_data.expires_at - datetime.utcnow()).total_seconds())
        if remaining_ttl > 0:
            await self.redis_client.setex(
                key,
                remaining_ttl,
                value.encode('utf-8')
            )

    async def rotate_session(self, old_session_id: str) -> SessionData | None:
        """Rotate session ID to prevent session fixation"""
        old_session = await self.get_session(old_session_id)
        if not old_session:
            return None

        # Create new session with same data but new ID
        new_session_id = str(uuid.uuid4())
        new_session = SessionData(
            session_id=new_session_id,
            user_id=old_session.user_id,
            user_info=old_session.user_info,
            created_at=old_session.created_at,
            last_accessed=datetime.utcnow(),
            expires_at=old_session.expires_at
        )

        # Store new session
        key = f"session:{new_session_id}"
        value = new_session.json()

        remaining_ttl = int((new_session.expires_at - datetime.utcnow()).total_seconds())
        if remaining_ttl > 0:
            await self.redis_client.setex(
                key,
                remaining_ttl,
                value.encode('utf-8')
            )

        # Delete old session
        await self.delete_session(old_session_id)

        return new_session

    async def delete_session(self, session_id: str):
        """Delete session"""
        if not self.redis_client:
            await self.initialize()

        key = f"session:{session_id}"
        await self.redis_client.delete(key)

    async def is_session_valid(self, session_id: str) -> bool:
        """Check if session is valid and not expired"""
        session = await self.get_session(session_id)
        if not session:
            return False

        return not session.is_expired()

    async def extend_session(self, session_id: str, extend_seconds: int = None):
        """Extend session expiration"""
        if not self.redis_client:
            await self.initialize()

        if extend_seconds is None:
            extend_seconds = settings.SESSION_MAX_AGE

        session = await self.get_session(session_id)
        if not session:
            return False

        session.expires_at = datetime.utcnow() + timedelta(seconds=extend_seconds)
        await self.update_session(session)

        return True

    async def get_user_sessions(self, user_id: str) -> list[SessionData]:
        """Get all active sessions for a user"""
        if not self.redis_client:
            await self.initialize()

        pattern = "session:*"
        sessions = []

        async for key in self.redis_client.scan_iter(match=pattern):
            session_data = await self.redis_client.get(key)
            if session_data:
                try:
                    session_json = session_data.decode('utf-8')
                    session_dict = json.loads(session_json)
                    session = SessionData(**session_dict)

                    if session.user_id == user_id and not session.is_expired():
                        sessions.append(session)
                except (json.JSONDecodeError, ValueError):
                    continue

        return sessions

    async def revoke_user_sessions(self, user_id: str):
        """Revoke all sessions for a user"""
        sessions = await self.get_user_sessions(user_id)
        for session in sessions:
            await self.delete_session(session.session_id)

    async def cleanup_expired_sessions(self):
        """Clean up expired sessions (maintenance task)"""
        if not self.redis_client:
            await self.initialize()

        pattern = "session:*"
        cleaned_count = 0

        async for key in self.redis_client.scan_iter(match=pattern):
            session_data = await self.redis_client.get(key)
            if session_data:
                try:
                    session_json = session_data.decode('utf-8')
                    session_dict = json.loads(session_json)
                    session = SessionData(**session_dict)

                    if session.is_expired():
                        await self.redis_client.delete(key)
                        cleaned_count += 1
                except (json.JSONDecodeError, ValueError):
                    # Invalid session data, delete it
                    await self.redis_client.delete(key)
                    cleaned_count += 1

        return cleaned_count


# Global instance
session_manager = SessionManager()
