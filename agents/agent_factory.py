"""Agent factory for generating company-specific agent code"""
import os
from pathlib import Path
from typing import Dict, Any


def generate_company_agent_code(
    company_id: str,
    company_name: str,
    memory_id: str,
    vector_db_namespace: str
) -> str:
    """Generate company-specific agent Python code"""
    
    # Read the base template
    template_path = Path(__file__).parent / "company_agent.py"
    with open(template_path, 'r') as f:
        template = f.read()
    
    # Replace placeholders with company-specific values
    code = template.replace(
        'COMPANY_ID = os.getenv("COMPANY_ID", "default-company")',
        f'COMPANY_ID = "{company_id}"'
    )
    code = code.replace(
        'COMPANY_NAME = os.getenv("COMPANY_NAME", "Default Company")',
        f'COMPANY_NAME = "{company_name}"'
    )
    code = code.replace(
        'MEMORY_ID = os.getenv("MEMORY_ID", "default-memory")',
        f'MEMORY_ID = "{memory_id}"'
    )
    code = code.replace(
        'VECTOR_DB_NAMESPACE = os.getenv("VECTOR_DB_NAMESPACE", f"company_{{COMPANY_ID}}")',
        f'VECTOR_DB_NAMESPACE = "{vector_db_namespace}"'
    )
    
    # Update system prompt with actual company name
    code = code.replace(
        'f"""You are a helpful FAQ assistant for {COMPANY_NAME}',
        f'"""You are a helpful FAQ assistant for {company_name}'
    )
    
    return code


def create_company_agent_file(
    company_id: str,
    company_name: str,
    memory_id: str,
    vector_db_namespace: str,
    output_dir: Path = None
) -> Path:
    """Create a company-specific agent Python file"""
    if output_dir is None:
        output_dir = Path(__file__).parent
    
    # Generate code
    agent_code = generate_company_agent_code(
        company_id=company_id,
        company_name=company_name,
        memory_id=memory_id,
        vector_db_namespace=vector_db_namespace
    )
    
    # Write to file
    agent_file = output_dir / f"company_agent_{company_id}.py"
    with open(agent_file, 'w') as f:
        f.write(agent_code)
    
    return agent_file


def generate_company_agent_code_stateless(
    company_id: str,
    company_name: str,
    vector_db_namespace: str
) -> str:
    """Generate stateless company-specific agent Python code (NO memory)"""
    
    # Read the stateless template
    template_path = Path(__file__).parent / "company_agent_stateless.py"
    with open(template_path, 'r') as f:
        template = f.read()
    
    # Replace placeholders with company-specific values
    # Replace COMPANY_ID placeholder
    code = template.replace(
        'COMPANY_ID = "PLACEHOLDER_COMPANY_ID"',
        f'COMPANY_ID = "{company_id}"'
    )
    
    # Replace COMPANY_NAME placeholder
    code = code.replace(
        'COMPANY_NAME = "PLACEHOLDER_COMPANY_NAME"',
        f'COMPANY_NAME = "{company_name}"'
    )
    
    # Replace VECTOR_DB_NAMESPACE placeholder
    code = code.replace(
        'VECTOR_DB_NAMESPACE = "PLACEHOLDER_VECTOR_DB_NAMESPACE"',
        f'VECTOR_DB_NAMESPACE = "{vector_db_namespace}"'
    )
    
    # Replace all occurrences in system prompt
    code = code.replace('PLACEHOLDER_COMPANY_ID', company_id)
    code = code.replace('PLACEHOLDER_COMPANY_NAME', company_name)
    code = code.replace('PLACEHOLDER_VECTOR_DB_NAMESPACE', vector_db_namespace)
    
    return code


def create_company_agent_file_stateless(
    company_id: str,
    company_name: str,
    vector_db_namespace: str,
    output_dir: Path = None
) -> Path:
    """Create a stateless company-specific agent Python file (NO memory)"""
    if output_dir is None:
        output_dir = Path(__file__).parent
    
    # Generate code
    agent_code = generate_company_agent_code_stateless(
        company_id=company_id,
        company_name=company_name,
        vector_db_namespace=vector_db_namespace
    )
    
    # Write to file (will be copied into Docker image)
    agent_file = output_dir / f"company_agent_{company_id}_stateless.py"
    with open(agent_file, 'w') as f:
        f.write(agent_code)
    
    return agent_file
