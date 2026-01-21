"""Data isolation tests - Critical for multi-tenant security"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import db
from backend.auth import get_password_hash, create_access_token

client = TestClient(app)


@pytest.fixture
def two_companies():
    """Create two test companies with users"""
    import uuid
    
    # Company 1
    company1_id = str(uuid.uuid4())
    user1_id = str(uuid.uuid4())
    db.create_company(company1_id, "Company 1", f"namespace_{company1_id}")
    user1 = db.create_user(
        user_id=user1_id,
        email="user1@company1.com",
        password_hash=get_password_hash("password123"),
        company_id=company1_id,
        role="employee"
    )
    
    # Company 2
    company2_id = str(uuid.uuid4())
    user2_id = str(uuid.uuid4())
    db.create_company(company2_id, "Company 2", f"namespace_{company2_id}")
    user2 = db.create_user(
        user_id=user2_id,
        email="user2@company2.com",
        password_hash=get_password_hash("password123"),
        company_id=company2_id,
        role="employee"
    )
    
    return {
        "company1": {"id": company1_id, "user": user1},
        "company2": {"id": company2_id, "user": user2},
    }


def test_user_cannot_access_other_company_data(two_companies):
    """Test that a user from Company 1 cannot access Company 2's data"""
    # Login as Company 1 user
    login_response = client.post("/auth/login", json={
        "email": "user1@company1.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    
    # Try to access Company 2's info (should fail)
    # Note: This test depends on the actual endpoint implementation
    # The company panel endpoint should only return the user's own company info
    response = client.get(
        "/company/info",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    # Verify it returns Company 1's info, not Company 2's
    assert response.json()["company_id"] == two_companies["company1"]["id"]
    assert response.json()["company_id"] != two_companies["company2"]["id"]


def test_admin_can_access_all_companies():
    """Test that admin users can access all companies"""
    import uuid
    # Create admin user
    admin_id = str(uuid.uuid4())
    admin = db.create_user(
        user_id=admin_id,
        email="admin@test.com",
        password_hash=get_password_hash("admin123"),
        company_id="",  # Admin might not belong to a company
        role="admin"
    )
    
    # Create token
    token = create_access_token({
        "sub": admin_id,
        "email": "admin@test.com",
        "company_id": "",
        "role": "admin"
    })
    
    # Admin should be able to list all companies
    response = client.get(
        "/admin/companies",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


def test_company_isolation_in_vector_search():
    """Test that vector search is isolated by company namespace"""
    # This test would verify that when searching, only the company's namespace is queried
    # Implementation depends on vector database setup
    pass


def test_agent_company_id_validation():
    """Test that agents validate company_id matches their own"""
    # This test would verify that agents reject requests with mismatched company_id
    # Implementation depends on agent deployment
    pass
