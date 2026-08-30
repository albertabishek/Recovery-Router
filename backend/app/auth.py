import hmac
from fastapi import Depends, HTTPException, Header
from app.config import settings


def require_auth(authorization: str = Header(None)):
    """Validate the Authorization header against APP_PASSWORD.
    Accepts: 'Bearer <password>' or plain '<password>'.
    """
    if not settings.APP_PASSWORD:
        raise HTTPException(status_code=500, detail="APP_PASSWORD not configured on server")

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:]

    if not hmac.compare_digest(token, settings.APP_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid password")

    return True


def verify_login(password: str) -> bool:
    """Check if a password matches APP_PASSWORD."""
    if not settings.APP_PASSWORD:
        return False
    return hmac.compare_digest(password, settings.APP_PASSWORD)
