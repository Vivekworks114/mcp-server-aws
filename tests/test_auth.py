"""Authentication tests"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import db
from backend.auth import get_password_hash

client = TestClient(app)


@pytest.fixture
def test_user():
    """Create a test user"""
    import uuid
    user_id = str(uuid.uuid4())
    company_id = str(uuid.uuid4())
    
    # Create test company
    db.create_company(company_id, "Test Company", f"namespace_{company_id}")
    
    # Create test user
    user = db.create_user(
        user_id=user_id,
        email="test@example.com",
        password_hash=get_password_hash("testpassword123"),
        company_id=company_id,
        role="employee"
    )
    
    yield user
    
    # Cleanup (if needed)


def test_login_success(test_user):
    """Test successful login"""
    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["user_id"] == test_user["user_id"]


def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    response = client.post("/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401


def test_protected_route_without_token():
    """Test accessing protected route without token"""
    response = client.get("/auth/me")
    assert response.status_code == 403


def test_protected_route_with_token(test_user):
    """Test accessing protected route with valid token"""
    # Login first
    login_response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123"
    })
    token = login_response.json()["access_token"]
    
    # Access protected route
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
