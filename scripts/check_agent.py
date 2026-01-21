#!/usr/bin/env python3
"""
Check if an agent exists for a company
Usage: python scripts/check_agent.py <company_id>
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.database import db

if len(sys.argv) < 2:
    print("Usage: python scripts/check_agent.py <company_id>")
    sys.exit(1)

company_id = sys.argv[1]

print(f"Checking agent for company: {company_id}")
print("-" * 60)

# Check company
company = db.get_company(company_id)
if not company:
    print(f"❌ Company not found: {company_id}")
    sys.exit(1)

print(f"✅ Company found: {company.get('name')}")
print(f"   Company ID: {company.get('company_id')}")
print(f"   Agent ID (from company record): {company.get('agent_id', 'None')}")

# Check agent by company_id
agent = db.get_agent_by_company(company_id)
if not agent:
    print(f"\n❌ No agent found for company_id: {company_id}")
    print("\nPossible reasons:")
    print("  1. Agent was never deployed for this company")
    print("  2. Agent deployment is still in progress")
    print("  3. Database eventual consistency delay")
    print("\nSolution:")
    print(f"  - Deploy/redeploy agent for this company via Admin Panel")
    print(f"  - Or via API: POST /admin/companies/{company_id}/agent/redeploy")
    sys.exit(1)

print(f"\n✅ Agent found!")
print(f"   Agent ID: {agent.get('agent_id')}")
print(f"   Company ID: {agent.get('company_id')}")
print(f"   Status: {agent.get('deployment_status', 'unknown')}")
print(f"   Agent ARN: {agent.get('agent_arn', 'None')}")
print(f"   ECR URI: {agent.get('ecr_uri', 'None')}")

if agent.get('deployment_status') != 'active':
    print(f"\n⚠️  Warning: Agent status is '{agent.get('deployment_status')}', not 'active'")
    print("   The agent may not be ready for use yet.")

if not agent.get('agent_arn'):
    print(f"\n⚠️  Warning: Agent ARN is missing")
    print("   The agent runtime may not be fully deployed.")

print("\n" + "-" * 60)
print("Agent record details:")
for key, value in agent.items():
    if key not in ['deployment_logs']:  # Skip logs for cleaner output
        print(f"  {key}: {value}")
