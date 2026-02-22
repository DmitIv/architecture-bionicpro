import jwt
import requests

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

security = HTTPBearer()


def get_keycloak_public_key():
    url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Could not fetch Keycloak public key")

    keys = response.json().get("keys", [])
    if not keys:
        raise HTTPException(status_code=500, detail="No public keys found")

    return jwt.algorithms.RSAAlgorithm.from_jwk(keys[0])


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        token = credentials.credentials
        public_key = get_keycloak_public_key()

        payload = jwt.decode(
            token,
            public_key,
            algorithms=settings.jwt_algorithms,
            audience="account"
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")


def get_current_user_id(payload: dict = Security(verify_token)):
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    return user_id
