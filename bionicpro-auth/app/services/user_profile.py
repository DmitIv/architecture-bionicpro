import logging

from datetime import datetime
from typing import Any

import aiohttp
import asyncpg

from fastapi import HTTPException

from ..config import settings
from ..models import ConsentRequest, ConsentResponse, UserProfile

logger = logging.getLogger(__name__)


class UserProfileService:
    """Service for managing user profiles from Yandex ID integration."""

    def __init__(self):
        self.db_pool: asyncpg.Pool | None = None

    async def initialize(self):
        """Initialize database connection pool."""
        try:
            self.db_pool = await asyncpg.create_pool(
                settings.postgres_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def close(self):
        """Close database connection pool."""
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Database connection pool closed")

    async def fetch_yandex_profile(self, access_token: str) -> dict[str, Any]:
        """
        Fetch user profile from Yandex API.

        Args:
            access_token: Yandex OAuth access token

        Returns:
            Dictionary containing user profile data from Yandex

        Raises:
            HTTPException: If API request fails
        """
        headers = {
            "Authorization": f"OAuth {access_token}",
            "Accept": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    settings.YANDEX_USERINFO_URL,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        profile_data = await response.json()
                        logger.info("Successfully fetched Yandex profile")
                        return profile_data
                    elif response.status == 401:
                        logger.error("Yandex access token expired or invalid")
                        raise HTTPException(
                            status_code=401,
                            detail="Yandex access token expired or invalid"
                        )
                    else:
                        error_text = await response.text()
                        logger.error(f"Yandex API error: {response.status} - {error_text}")
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Failed to fetch Yandex profile: {error_text}"
                        )
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching Yandex profile: {e}")
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable"
            )
        except TimeoutError:
            logger.error("Timeout fetching Yandex profile")
            raise HTTPException(
                status_code=504,
                detail="Request timeout"
            )

    async def store_user_profile(self, user_id: str, profile_data: dict[str, Any]) -> UserProfile:
        """
        Store user profile in database.

        Args:
            user_id: Keycloak user ID
            profile_data: Profile data from Yandex API

        Returns:
            Created/updated UserProfile
        """
        if not self.db_pool:
            raise HTTPException(
                status_code=500,
                detail="Database not initialized"
            )

        user_profile = UserProfile.from_yandex_profile(user_id, profile_data)

        try:
            async with self.db_pool.acquire() as conn:
                # Check if profile already exists
                existing = await conn.fetchrow(
                    "SELECT id FROM user_profiles WHERE user_id = $1",
                    user_id
                )

                if existing:
                    # Update existing profile
                    await conn.execute(
                        """
                        UPDATE user_profiles SET
                            yandex_id = $2,
                            username = $3,
                            email = $4,
                            first_name = $5,
                            last_name = $6,
                            display_name = $7,
                            avatar_url = $8,
                            phone = $9,
                            birthday = $10,
                            gender = $11,
                            profile_data = $12,
                            consent_given = $13,
                            consent_timestamp = $14,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = $1
                        """,
                        user_id,
                        user_profile.yandex_id,
                        user_profile.username,
                        user_profile.email,
                        user_profile.first_name,
                        user_profile.last_name,
                        user_profile.display_name,
                        user_profile.avatar_url,
                        user_profile.phone,
                        user_profile.birthday,
                        user_profile.gender,
                        user_profile.profile_data,
                        user_profile.consent_given,
                        datetime.utcnow() if user_profile.consent_given else None
                    )
                    logger.info(f"Updated user profile for user_id: {user_id}")
                else:
                    # Insert new profile
                    await conn.execute(
                        """
                        INSERT INTO user_profiles (
                            user_id, yandex_id, username, email, first_name, last_name,
                            display_name, avatar_url, phone, birthday, gender,
                            profile_data, consent_given, consent_timestamp
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        """,
                        user_id,
                        user_profile.yandex_id,
                        user_profile.username,
                        user_profile.email,
                        user_profile.first_name,
                        user_profile.last_name,
                        user_profile.display_name,
                        user_profile.avatar_url,
                        user_profile.phone,
                        user_profile.birthday,
                        user_profile.gender,
                        user_profile.profile_data,
                        user_profile.consent_given,
                        datetime.utcnow() if user_profile.consent_given else None
                    )
                    logger.info(f"Created new user profile for user_id: {user_id}")

                # Return the stored profile
                return await self.get_user_profile(user_id)

        except asyncpg.PostgresError as e:
            logger.error(f"Database error storing user profile: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to store user profile"
            )

    async def get_user_profile(self, user_id: str) -> UserProfile:
        """
        Retrieve user profile from database.

        Args:
            user_id: Keycloak user ID

        Returns:
            UserProfile object

        Raises:
            HTTPException: If profile not found
        """
        if not self.db_pool:
            raise HTTPException(
                status_code=500,
                detail="Database not initialized"
            )

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, user_id, yandex_id, username, email, first_name, last_name,
                           display_name, avatar_url, phone, birthday, gender,
                           profile_data, consent_given, consent_timestamp,
                           created_at, updated_at
                    FROM user_profiles
                    WHERE user_id = $1
                    """,
                    user_id
                )

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="User profile not found"
                    )

                return UserProfile(
                    id=row["id"],
                    user_id=row["user_id"],
                    yandex_id=row["yandex_id"],
                    username=row["username"],
                    email=row["email"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    display_name=row["display_name"],
                    avatar_url=row["avatar_url"],
                    phone=row["phone"],
                    birthday=row["birthday"].isoformat() if row["birthday"] else None,
                    gender=row["gender"],
                    profile_data=row["profile_data"],
                    consent_given=row["consent_given"],
                    consent_timestamp=(
                        row["consent_timestamp"].isoformat()
                        if row["consent_timestamp"] else None
                    ),
                    created_at=row["created_at"].isoformat() if row["created_at"] else None,
                    updated_at=row["updated_at"].isoformat() if row["updated_at"] else None
                )

        except asyncpg.PostgresError as e:
            logger.error(f"Database error retrieving user profile: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve user profile"
            )

    async def update_user_profile(self, user_id: str, profile_data: dict[str, Any]) -> UserProfile:
        """
        Update existing user profile.

        Args:
            user_id: Keycloak user ID
            profile_data: Updated profile data

        Returns:
            Updated UserProfile
        """
        return await self.store_user_profile(user_id, profile_data)

    async def delete_user_profile(self, user_id: str) -> bool:
        """
        Delete user profile from database.

        Args:
            user_id: Keycloak user ID

        Returns:
            True if profile was deleted, False if not found
        """
        if not self.db_pool:
            raise HTTPException(
                status_code=500,
                detail="Database not initialized"
            )

        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM user_profiles WHERE user_id = $1",
                    user_id
                )

                deleted_count = int(result.split()[-1]) if result else 0
                if deleted_count > 0:
                    logger.info(f"Deleted user profile for user_id: {user_id}")
                    return True
                else:
                    logger.warning(f"No profile found to delete for user_id: {user_id}")
                    return False

        except asyncpg.PostgresError as e:
            logger.error(f"Database error deleting user profile: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to delete user profile"
            )

    async def process_consent(self, consent_request: ConsentRequest, consent_given: bool) -> ConsentResponse:
        """
        Process user consent for profile data storage.

        Args:
            consent_request: Consent request with user data
            consent_given: Whether user gave consent

        Returns:
            ConsentResponse with result
        """
        try:
            if consent_given:
                # Store profile with consent
                user_profile = await self.store_user_profile(
                    consent_request.user_id,
                    consent_request.yandex_profile
                )

                logger.info(f"User {consent_request.user_id} gave consent for profile storage")

                return ConsentResponse(
                    success=True,
                    message="Profile data stored successfully",
                    user_profile=user_profile,
                    redirect_url=consent_request.redirect_url
                )
            else:
                # User denied consent - don't store profile
                logger.info(f"User {consent_request.user_id} denied consent for profile storage")

                return ConsentResponse(
                    success=False,
                    message="User denied consent - profile data not stored",
                    redirect_url=consent_request.redirect_url
                )

        except Exception as e:
            logger.error(f"Error processing consent: {e}")
            return ConsentResponse(
                success=False,
                message=f"Error processing consent: {str(e)}"
            )


# Global instance
user_profile_service = UserProfileService()
