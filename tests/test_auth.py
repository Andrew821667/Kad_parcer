"""Tests for authentication system."""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.app import app
from src.api.auth import create_access_token, decode_access_token, get_password_hash, verify_password
from src.core.exceptions import UnauthorizedException
from src.storage.database.auth_models import APIKey, User


class TestPasswordHashing:
    """Test password hashing functions."""

    def test_hash_password(self) -> None:
        """Test password hashing."""
        password = "test_password123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")

    def test_verify_password_success(self) -> None:
        """Test password verification with correct password."""
        password = "test_password123"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_failure(self) -> None:
        """Test password verification with incorrect password."""
        password = "test_password123"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False


class TestJWT:
    """Test JWT token functions."""

    def test_create_access_token(self) -> None:
        """Test JWT token creation."""
        data = {"sub": 1, "username": "testuser"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_expiration(self) -> None:
        """Test JWT token creation with custom expiration."""
        data = {"sub": 1, "username": "testuser"}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta=expires_delta)

        payload = decode_access_token(token)
        assert payload["sub"] == 1
        assert payload["username"] == "testuser"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_access_token(self) -> None:
        """Test JWT token decoding."""
        data = {"sub": 1, "username": "testuser"}
        token = create_access_token(data)

        payload = decode_access_token(token)
        assert payload["sub"] == 1
        assert payload["username"] == "testuser"

    def test_decode_invalid_token(self) -> None:
        """Test decoding invalid token."""
        with pytest.raises(UnauthorizedException):
            decode_access_token("invalid_token")


class TestAPIKeyModel:
    """Test APIKey model."""

    def test_generate_key(self) -> None:
        """Test API key generation."""
        key = APIKey.generate_key()

        assert isinstance(key, str)
        assert key.startswith("kad_")
        assert len(key) > 10


class TestAuthEndpoints:
    """Test authentication endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    async def test_user(self, async_session: AsyncSession) -> User:
        """Create test user."""
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password=get_password_hash("testpass123"),
            is_active=True,
            is_superuser=False,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_register_success(self, client: TestClient) -> None:
        """Test successful user registration."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "newpass123",
                "full_name": "New User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert data["full_name"] == "New User"
        assert data["is_active"] is True
        assert data["is_superuser"] is False
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: TestClient, test_user: User) -> None:
        """Test registration with duplicate email."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": test_user.email,
                "username": "different_username",
                "password": "testpass123",
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: TestClient, test_user: User) -> None:
        """Test registration with duplicate username."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "different@example.com",
                "username": test_user.username,
                "password": "testpass123",
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_success(self, client: TestClient, test_user: User) -> None:
        """Test successful login."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": test_user.username,
                "password": "testpass123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: TestClient, test_user: User) -> None:
        """Test login with wrong password."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": test_user.username,
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: TestClient) -> None:
        """Test login with nonexistent user."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent",
                "password": "testpass123",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_info(self, client: TestClient, test_user: User) -> None:
        """Test getting current user info."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": test_user.username,
                "password": "testpass123",
            },
        )
        token = login_response.json()["access_token"]

        # Get user info
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_get_current_user_info_no_token(self, client: TestClient) -> None:
        """Test getting current user info without token."""
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_api_key(self, client: TestClient, test_user: User) -> None:
        """Test API key creation."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": test_user.username,
                "password": "testpass123",
            },
        )
        token = login_response.json()["access_token"]

        # Create API key
        response = client.post(
            "/api/auth/api-keys",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Test API Key",
                "expires_days": 30,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test API Key"
        assert data["key"].startswith("kad_")
        assert data["is_active"] is True
        assert data["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_list_api_keys(self, client: TestClient, test_user: User) -> None:
        """Test listing API keys."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": test_user.username,
                "password": "testpass123",
            },
        )
        token = login_response.json()["access_token"]

        # Create API key
        client.post(
            "/api/auth/api-keys",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test Key 1"},
        )

        # List API keys
        response = client.get(
            "/api/auth/api-keys",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "Test Key 1"

    @pytest.mark.asyncio
    async def test_delete_api_key(
        self, client: TestClient, test_user: User, async_session: AsyncSession
    ) -> None:
        """Test deleting API key."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": test_user.username,
                "password": "testpass123",
            },
        )
        token = login_response.json()["access_token"]

        # Create API key
        create_response = client.post(
            "/api/auth/api-keys",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test Key to Delete"},
        )
        key_id = create_response.json()["id"]

        # Delete API key
        response = client.delete(
            f"/api/auth/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_nonexistent_api_key(self, client: TestClient, test_user: User) -> None:
        """Test deleting nonexistent API key."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": test_user.username,
                "password": "testpass123",
            },
        )
        token = login_response.json()["access_token"]

        # Try to delete nonexistent key
        response = client.delete(
            "/api/auth/api-keys/99999",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
