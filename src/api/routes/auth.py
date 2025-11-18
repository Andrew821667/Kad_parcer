"""Authentication routes."""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token, get_password_hash, verify_password
from src.api.dependencies import get_current_active_user, get_current_superuser
from src.core.logging import get_logger
from src.storage.database.auth_models import APIKey, User
from src.storage.database.base import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


class Token(BaseModel):
    """Token response."""

    access_token: str
    token_type: str = "bearer"


class UserLogin(BaseModel):
    """User login request."""

    username: str
    password: str


class UserCreate(BaseModel):
    """User creation request."""

    email: EmailStr
    username: str
    password: str
    full_name: str | None = None


class UserResponse(BaseModel):
    """User response."""

    id: int
    email: str
    username: str
    full_name: str | None
    is_active: bool
    is_superuser: bool

    model_config = {"from_attributes": True}


class APIKeyCreate(BaseModel):
    """API key creation request."""

    name: str
    expires_days: int | None = None


class APIKeyResponse(BaseModel):
    """API key response."""

    id: int
    name: str
    key: str
    is_active: bool
    expires_at: str | None

    model_config = {"from_attributes": True}


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Register new user."""
    # Check if user exists
    result = await db.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )

    # Create user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("user_registered", user_id=user.id, username=user.username)
    return user


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Login user and get JWT token."""
    # Find user
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username}
    )

    logger.info("user_logged_in", user_id=user.id, username=user.username)

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get current user info."""
    return current_user


@router.post("/api-keys", response_model=APIKeyResponse, status_code=201)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create new API key for current user."""
    from datetime import datetime

    api_key = APIKey(
        user_id=current_user.id,
        name=key_data.name,
        key=APIKey.generate_key(),
        expires_at=(
            datetime.utcnow() + timedelta(days=key_data.expires_days)
            if key_data.expires_days
            else None
        ),
    )

    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    logger.info("api_key_created", user_id=current_user.id, key_name=key_data.name)

    return api_key


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List all API keys for current user."""
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id)
    )
    api_keys = result.scalars().all()

    return api_keys


@router.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete API key."""
    result = await db.execute(
        select(APIKey).where(
            (APIKey.id == key_id) & (APIKey.user_id == current_user.id)
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(api_key)
    await db.commit()

    logger.info("api_key_deleted", user_id=current_user.id, key_id=key_id)
