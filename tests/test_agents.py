"""Agent deployment and invocation tests"""
import pytest
from backend.database import db
from agents.agent_factory import generate_company_agent_code, create_company_agent_file
from pathlib import Path
import tempfile


def test_agent_factory_generates_company_specific_code():
    """Test that agent factory generates code with company-specific values"""
    company_id = "test-company-123"
    company_name = "Test Company"
    memory_id = "test-memory-123"
    namespace = "test-namespace"
    
    code = generate_company_agent_code(
        company_id=company_id,
        company_name=company_name,
        memory_id=memory_id,
        vector_db_namespace=namespace
    )
    
    # Verify company-specific values are in the code
    assert company_id in code
    assert company_name in code
    assert memory_id in code
    assert namespace in code
    
    # Verify isolation guardrails are present
    assert "COMPANY_ID" in code
    assert "data isolation" in code.lower() or "isolation" in code.lower()


def test_agent_factory_creates_file():
    """Test that agent factory creates a file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir)
        
        file_path = create_company_agent_file(
            company_id="test-123",
            company_name="Test",
            memory_id="memory-123",
            vector_db_namespace="namespace-123",
            output_dir=output_path
        )
        
        assert file_path.exists()
        assert file_path.name.startswith("company_agent_")
        
        # Verify file content
        content = file_path.read_text()
        assert "test-123" in content


def test_agent_code_contains_isolation_middleware():
    """Test that generated agent code contains isolation middleware"""
    code = generate_company_agent_code(
        company_id="test",
        company_name="Test",
        memory_id="memory",
        vector_db_namespace="namespace"
    )
    
    # Verify middleware is present
    assert "CompanyIsolationMiddleware" in code
    assert "company_id" in code.lower()
