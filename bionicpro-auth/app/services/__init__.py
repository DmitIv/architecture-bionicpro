"""
Services package for BionicPRO authentication.

This package contains business logic services for handling various aspects
of the authentication system, including user profile management.
"""

from .user_profile import UserProfileService, user_profile_service

__all__ = ["UserProfileService", "user_profile_service"]
