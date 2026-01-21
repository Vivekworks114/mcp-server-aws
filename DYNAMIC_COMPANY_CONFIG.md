# Dynamic Company Configuration

## Overview

The agent deployment system now dynamically injects company-specific configuration when creating or redeploying agents. Company data (ID, name, vector DB namespace) is injected at build time into the Docker container.

## How It Works

### 1. Template with Placeholders

The `agents/company_agent_stateless.py` template uses placeholders that are replaced during agent file generation:

```python
COMPANY_ID = "PLACEHOLDER_COMPANY_ID"
COMPANY_NAME = "PLACEHOLDER_COMPANY_NAME"
VECTOR_DB_NAMESPACE = "PLACEHOLDER_VECTOR_DB_NAMESPACE"
```

The system prompt also uses these placeholders:
```python
system_prompt = """You are a helpful FAQ assistant for PLACEHOLDER_COMPANY_NAME (Company ID: PLACEHOLDER_COMPANY_ID).
...
"""
```

### 2. Dynamic Replacement

When a company is created or an agent is redeployed, `agents/agent_factory.py`:

1. Reads the template file
2. Replaces all placeholders with actual company values:
   - `PLACEHOLDER_COMPANY_ID` → actual company ID
   - `PLACEHOLDER_COMPANY_NAME` → actual company name
   - `PLACEHOLDER_VECTOR_DB_NAMESPACE` → actual vector DB namespace
3. Generates a company-specific agent file: `company_agent_{company_id}_stateless.py`

### 3. Docker Build

The generated company-specific file is:
1. Copied to `company_agent_stateless.py` in the build context
2. Built into a Docker image with company-specific code baked in
3. Tagged with the company ID: `{ecr_uri}:{company_id}`
4. Pushed to ECR

### 4. Runtime

The container runs with company-specific code already embedded. No environment variable injection needed at runtime for company identification.

## Deployment Flow

### New Company Creation

1. **Admin creates company** via `/admin/companies` endpoint
2. **Agent record created** with `deployment_status: "pending"`
3. **Background task starts** deployment:
   - Generates company-specific agent code
   - Builds Docker image with company data
   - Pushes to ECR
   - Creates agent runtime via Bedrock API
4. **Status updates** to `active` when ready

### Agent Redeployment

1. **Admin triggers redeploy** via `/admin/companies/{company_id}/agent/redeploy`
2. **Deployment function**:
   - Gets current company data from database
   - Regenerates agent code with latest company info
   - Rebuilds Docker image
   - Pushes new image to ECR (same tag, new digest)
   - Updates agent runtime (if needed)
3. **Status updates** to `deploying` → `active`

## Key Benefits

1. **Dynamic Configuration**: Each company gets its own agent with correct company data
2. **Isolation**: Company data is baked into the container, ensuring isolation
3. **Real-time Updates**: Redeployment uses current company data from database
4. **No Runtime Secrets**: Company identification doesn't require environment variables
5. **Version Control**: Each company has its own Docker image tag

## Code Changes

### Template (`agents/company_agent_stateless.py`)
- Changed hardcoded values to placeholders
- System prompt uses placeholders

### Factory (`agents/agent_factory.py`)
- `generate_company_agent_code_stateless()` replaces all placeholders
- Handles both variable assignments and system prompt

### Deployer (`backend/utils/agent_deployer.py`)
- Already handles dynamic company data correctly
- Redeploy flow uses existing agent_id and regenerates code

## Testing

To verify dynamic configuration:

1. **Create a new company**:
   ```bash
   POST /admin/companies
   {
     "name": "Test Company",
     "admin_email": "admin@test.com",
     "admin_password": "password123"
   }
   ```

2. **Check generated agent file**:
   ```bash
   cat agents/company_agent_{company_id}_stateless.py
   # Should show actual company ID, name, namespace
   ```

3. **Verify Docker image**:
   ```bash
   docker inspect {ecr_uri}:{company_id}
   # Image should contain company-specific code
   ```

4. **Redeploy agent**:
   ```bash
   POST /admin/companies/{company_id}/agent/redeploy
   # Should regenerate with latest company data
   ```

## Notes

- Company data is fetched from database at deployment time
- If company name changes, redeploy to update agent
- Vector DB namespace is derived from company_id if not explicitly set
- Each company gets a unique Docker image tag for versioning
