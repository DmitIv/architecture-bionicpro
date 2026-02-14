import base64
import hashlib
import secrets
import urllib.parse

import httpx

from ..config import settings
from ..models import PKCEChallenge, TokenInfo, UserInfo


class KeycloakClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    def generate_pkce_challenge(self) -> PKCEChallenge:
        """Generate PKCE code verifier and challenge"""
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        return PKCEChallenge(
            code_verifier=code_verifier,
            code_challenge=code_challenge
        )

    def get_authorization_url(self, pkce_challenge: PKCEChallenge, redirect_uri: str, state: str) -> str:
        """Build Keycloak authorization URL with PKCE"""
        params = {
            'response_type': 'code',
            'client_id': settings.KEYCLOAK_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'scope': 'openid profile email',
            'state': state,
            'code_challenge': pkce_challenge.code_challenge,
            'code_challenge_method': pkce_challenge.challenge_method
        }

        return f"{settings.keycloak_auth_url}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str, pkce_challenge: PKCEChallenge, redirect_uri: str) -> TokenInfo:
        """Exchange authorization code for tokens"""
        data = {
            'grant_type': 'authorization_code',
            'client_id': settings.KEYCLOAK_CLIENT_ID,
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': pkce_challenge.code_verifier
        }

        if settings.KEYCLOAK_CLIENT_SECRET:
            data['client_secret'] = settings.KEYCLOAK_CLIENT_SECRET

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = await self.client.post(
            settings.keycloak_token_url,
            data=data,
            headers=headers
        )

        response.raise_for_status()
        token_data = response.json()

        return TokenInfo(
            access_token=token_data['access_token'],
            refresh_token=token_data['refresh_token'],
            token_type=token_data.get('token_type', 'Bearer'),
            expires_in=token_data['expires_in'],
            refresh_expires_in=token_data['refresh_expires_in'],
            scope=token_data.get('scope', ''),
            id_token=token_data.get('id_token')
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenInfo:
        """Refresh access token using refresh token"""
        data = {
            'grant_type': 'refresh_token',
            'client_id': settings.KEYCLOAK_CLIENT_ID,
            'refresh_token': refresh_token
        }

        if settings.KEYCLOAK_CLIENT_SECRET:
            data['client_secret'] = settings.KEYCLOAK_CLIENT_SECRET

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = await self.client.post(
            settings.keycloak_token_url,
            data=data,
            headers=headers
        )

        response.raise_for_status()
        token_data = response.json()

        return TokenInfo(
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token', refresh_token),  # Use new refresh token if provided
            token_type=token_data.get('token_type', 'Bearer'),
            expires_in=token_data['expires_in'],
            refresh_expires_in=token_data['refresh_expires_in'],
            scope=token_data.get('scope', ''),
            id_token=token_data.get('id_token')
        )

    async def get_user_info(self, access_token: str) -> UserInfo:
        """Get user information from Keycloak"""
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        response = await self.client.get(
            settings.keycloak_userinfo_url,
            headers=headers
        )

        response.raise_for_status()
        user_claims = response.json()

        return UserInfo.from_keycloak_claims(user_claims)

    async def logout(self, refresh_token: str) -> bool:
        """Logout user from Keycloak"""
        data = {
            'client_id': settings.KEYCLOAK_CLIENT_ID,
            'refresh_token': refresh_token
        }

        if settings.KEYCLOAK_CLIENT_SECRET:
            data['client_secret'] = settings.KEYCLOAK_CLIENT_SECRET

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        try:
            response = await self.client.post(
                settings.keycloak_logout_url,
                data=data,
                headers=headers
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def validate_token(self, access_token: str) -> bool:
        """Validate access token by calling userinfo endpoint"""
        try:
            await self.get_user_info(access_token)
            return True
        except httpx.HTTPError:
            return False

    def get_logout_redirect_url(self, redirect_uri: str) -> str:
        """Get Keycloak logout redirect URL"""
        params = {
            'client_id': settings.KEYCLOAK_CLIENT_ID,
            'post_logout_redirect_uri': redirect_uri
        }

        return f"{settings.keycloak_logout_url}?{urllib.parse.urlencode(params)}"


# Global instance
keycloak_client = KeycloakClient()
