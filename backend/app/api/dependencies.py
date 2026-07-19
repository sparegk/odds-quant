from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = settings.admin_api_key
    if expected is None:
        if settings.environment.casefold() == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Administrative imports are disabled until ODDSQUANT_ADMIN_API_KEY is set",
            )
        return
    if x_admin_key is None or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrative API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
