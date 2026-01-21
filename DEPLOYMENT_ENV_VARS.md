# Environment Variables for Stateless Agent Deployment

This document describes all environment variables used in the production-grade stateless agent deployment system.

## Backend Environment Variables

### Required Variables

#### AWS Configuration
- **`AWS_REGION`** (default: `us-east-1`)
  - AWS region for all AWS services (ECR, Bedrock AgentCore, Secrets Manager, DynamoDB)
  - Example: `us-east-1`, `us-west-2`

- **`AWS_ACCESS_KEY_ID`**
  - AWS access key ID for programmatic access
  - Required for boto3 operations

- **`AWS_SECRET_ACCESS_KEY`**
  - AWS secret access key for programmatic access
  - Required for boto3 operations

#### IAM Role
- **`AGENTCORE_IAM_ROLE_ARN`**
  - IAM role ARN for AgentCore runtime execution
  - Must have permissions for:
    - Bedrock InvokeModel API
    - CloudWatch Logs (for agent logging)
    - ECR image pull (if using private ECR)
  - Format: `arn:aws:iam::<ACCOUNT_ID>:role/<ROLE_NAME>`
  - Example: `arn:aws:iam::123456789012:role/AgentCoreServiceRole`

#### ECR Configuration
- **`ECR_REPOSITORY_NAME`** (default: `agentcore-agents`)
  - Name of the ECR repository for storing agent container images
  - Will be created automatically if it doesn't exist
  - Example: `agentcore-agents`, `company-agents`

### Optional Variables

#### Vector Database (Pinecone)
- **`PINECONE_API_KEY`**
  - Pinecone API key (can also be stored in AWS Secrets Manager as `agentcore/pinecone-api-key`)
  - Required if using Pinecone for vector search

- **`PINECONE_INDEX_NAME`** (default: `mcp-server`)
  - Name of the Pinecone index to use
  - Example: `mcp-server`, `company-knowledge-base`

#### DynamoDB Tables (optional, defaults provided)
- **`COMPANIES_TABLE`** (default: `companies`)
- **`USERS_TABLE`** (default: `users`)
- **`AGENTS_TABLE`** (default: `agents`)
- **`AUDIT_LOGS_TABLE`** (default: `audit_logs`)

## Container Runtime Environment Variables

These variables are injected into the container at runtime via the `create_agent_runtime` API:

### Required
- **`COMPANY_ID`**
  - Unique identifier for the company
  - Injected automatically during deployment
  - Example: `a8c7b908-9e75-4e81-aa79-f8921e649a37`

- **`COMPANY_NAME`**
  - Display name of the company
  - Injected automatically during deployment
  - Example: `Acme Corporation`

- **`VECTOR_DB_NAMESPACE`**
  - Namespace for company-specific vector data isolation
  - Format: `company_<COMPANY_ID>`
  - Injected automatically during deployment

- **`GROQ_API_KEY`**
  - Groq API key for LLM inference
  - Retrieved from AWS Secrets Manager (`agentcore/groq-api-key`)
  - Injected automatically during deployment

### Optional
- **`HF_API_KEY`**
  - Hugging Face API token (for embeddings)
  - Retrieved from AWS Secrets Manager (`agentcore/huggingface-token`)
  - Can be empty if not using Hugging Face models

- **`PINECONE_API_KEY`**
  - Pinecone API key for vector search
  - Retrieved from AWS Secrets Manager (`agentcore/pinecone-api-key`) or environment variable
  - Required if using Pinecone

- **`PINECONE_INDEX_NAME`** (default: `mcp-server`)
  - Pinecone index name
  - Example: `mcp-server`

- **`AWS_REGION`**
  - AWS region (inherited from backend configuration)
  - Used for AWS SDK operations within the container

## AWS Secrets Manager Secrets

The deployment system expects the following secrets in AWS Secrets Manager:

### Required
- **`agentcore/groq-api-key`**
  - Groq API key for LLM inference
  - Format: Plain text string

### Optional
- **`agentcore/huggingface-token`**
  - Hugging Face API token
  - Format: Plain text string
  - Can be empty if not using Hugging Face models

- **`agentcore/pinecone-api-key`**
  - Pinecone API key
  - Format: Plain text string
  - Can also be provided via `PINECONE_API_KEY` environment variable

## IAM Role Permissions

The IAM role specified in `AGENTCORE_IAM_ROLE_ARN` must have the following permissions:

### Bedrock Permissions
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": [
    "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
    "arn:aws:bedrock:*::foundation-model/amazon.titan-*"
  ]
}
```

### CloudWatch Logs Permissions
```json
{
  "Effect": "Allow",
  "Action": [
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:PutLogEvents"
  ],
  "Resource": "arn:aws:logs:*:*:*"
}
```

### ECR Permissions (if using private ECR)
```json
{
  "Effect": "Allow",
  "Action": [
    "ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability",
    "ecr:GetDownloadUrlForLayer",
    "ecr:BatchGetImage"
  ],
  "Resource": "*"
}
```

## Example `.env` File

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# IAM Role
AGENTCORE_IAM_ROLE_ARN=arn:aws:iam::123456789012:role/AgentCoreServiceRole

# ECR Configuration
ECR_REPOSITORY_NAME=agentcore-agents

# Vector Database (optional - can use Secrets Manager instead)
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=mcp-server

# DynamoDB Tables (optional - defaults provided)
COMPANIES_TABLE=companies
USERS_TABLE=users
AGENTS_TABLE=agents
AUDIT_LOGS_TABLE=audit_logs
```

## Notes

1. **Stateless Agents**: All agents are stateless - no memory or conversation persistence is maintained.

2. **Company Isolation**: Company data isolation is enforced via:
   - Vector database namespaces (`VECTOR_DB_NAMESPACE`)
   - Company ID validation in agent code
   - System prompts with company-specific guardrails

3. **Secrets Management**: Prefer AWS Secrets Manager over environment variables for sensitive data (API keys, tokens).

4. **ECR Repository**: The ECR repository is created automatically if it doesn't exist. Ensure the backend IAM user/role has `ecr:CreateRepository` permission.

5. **Docker Requirement**: Docker must be installed and running on the backend server for building and pushing container images.

6. **Network Mode**: Agents are deployed with `PUBLIC` network mode. For private networking, update the `networkConfiguration` in `agent_deployer.py`.
