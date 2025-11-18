"""Authentication dependencies for FastAPI."""

from datetime import datetime
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import decode_access_token
from src.core.exceptions import UnauthorizedException
from src.storage.database.auth_models import APIKey, User
from src.storage.database.base import get_db

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        User object or None if not authenticated

    Raises:
        UnauthorizedException: If token is invalid
    """
    if not credentials:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: int = payload.get("sub")

        if user_id is None:
            raise UnauthorizedException("Invalid token payload")

        # Get user from database
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise UnauthorizedException("User not found")

        if not user.is_active:
            raise UnauthorizedException("User is inactive")

        return user

    except UnauthorizedException:
        raise
    except Exception as e:
        raise UnauthorizedException(f"Authentication failed: {e}") from e


async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """Require authenticated user.

    Args:
        current_user: Current user from get_current_user

    Returns:
        User object

    Raises:
        HTTPException: If user is not authenticated
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Require superuser.

    Args:
        current_user: Current authenticated user

    Returns:
        User object

    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def verify_api_key(
    x_api_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[APIKey]:
    """Verify API key from header.

    Args:
        x_api_key: API key from X-API-Key header
        db: Database session

    Returns:
        APIKey object or None

    Raises:
        HTTPException: If API key is invalid
    """
    if not x_api_key:
        return None

    result = await db.execute(select(APIKey).where(APIKey.key == x_api_key))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive",
        )

    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    # Update last used timestamp
    api_key.last_used_at = datetime.utcnow()
    await db.commit()

    return api_key
