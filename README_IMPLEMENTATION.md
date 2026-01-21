# Multi-Company Agent System - Implementation Guide

## Overview

This implementation provides a complete multi-tenant agent system with:
- Separate AgentCore deployments per company
- Admin Panel for company management
- Company Panel for employee chat interactions
- Strict data isolation and security guardrails

## Architecture

- **Backend**: FastAPI with DynamoDB, JWT authentication
- **Agents**: AWS Bedrock AgentCore Runtime (one per company)
- **Vector DB**: Pinecone with company namespaces
- **Frontend**: Next.js (Admin Panel + Company Panel)
- **Storage**: DynamoDB for metadata, AWS Secrets Manager for credentials

## Setup Instructions

### 1. Prerequisites

- Python 3.13+
- Node.js 18+
- AWS Account with Bedrock AgentCore access
- AWS CLI configured
- Groq API key
- Hugging Face API token (optional but recommended)
- Pinecone API key (for vector database)

### 2. Backend Setup

```bash
# Install Python dependencies
uv sync

# Set up environment variables
cp .sample_env .env
# Edit .env with your credentials:
# - GROQ_API_KEY
# - HF_API_KEY
# - JWT_SECRET_KEY
# - PINECONE_API_KEY
# - AWS_REGION
# - AWS credentials (via AWS CLI or environment)

# Create DynamoDB tables
python scripts/create_tables.py  # (create this script if needed)
# Or use AWS Console/CLI with infrastructure/dynamodb_tables.json

# Store secrets in AWS Secrets Manager
aws secretsmanager create-secret --name agentcore/groq-api-key --secret-string "your-groq-key"
aws secretsmanager create-secret --name agentcore/huggingface-token --secret-string "your-hf-token"

# Run backend
cd backend
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup

#### Admin Panel
```bash
cd frontend/admin-panel
npm install
npm run dev  # Runs on http://localhost:3000
```

#### Company Panel
```bash
cd frontend/company-panel
npm install
npm run dev  # Runs on http://localhost:3001
```

### 4. Agent Deployment

Agents are automatically deployed when a company is created via the Admin Panel. The deployment process:

1. Creates company record in DynamoDB
2. Generates company-specific agent code
3. Deploys to AWS Bedrock AgentCore Runtime
4. Stores deployment metadata

## Key Features

### Data Isolation

- **API Level**: All endpoints validate `company_id` from JWT
- **Agent Level**: Each agent has hardcoded `COMPANY_ID` and validates incoming requests
- **Vector Search**: Namespace filtering ensures only company data is retrieved
- **Memory**: Namespace includes `company_id`: `(company_id, actor_id, thread_id)`

### Security

- JWT-based authentication
- Password hashing with bcrypt
- Role-based access control (admin/employee)
- Audit logging for all actions
- Input validation and sanitization

### Audit Logging

All actions are logged to DynamoDB:
- User logins
- Company creation/updates
- Agent invocations
- Knowledge base uploads
- User management

## Testing

```bash
# Run tests
pytest tests/

# Run specific test suite
pytest tests/test_isolation.py  # Critical: Data isolation tests
pytest tests/test_auth.py       # Authentication tests
pytest tests/test_agents.py     # Agent deployment tests
```

## Deployment

### Backend (AWS)
- Deploy FastAPI to ECS, Lambda, or App Runner
- Set environment variables
- Configure IAM roles for DynamoDB and Secrets Manager access

### Frontend (S3 + CloudFront)
```bash
# Admin Panel
cd frontend/admin-panel
npm run build
npm run export
aws s3 sync out/ s3://your-admin-panel-bucket/

# Company Panel
cd frontend/company-panel
npm run build
npm run export
aws s3 sync out/ s3://your-company-panel-bucket/
```

### Agents
- Agents are deployed automatically via `agentcore launch`
- Each agent runs in its own AgentCore Runtime instance
- Credentials are injected as environment variables

## Environment Variables

### Backend
- `JWT_SECRET_KEY`: Secret for JWT signing
- `AWS_REGION`: AWS region
- `COMPANIES_TABLE`: DynamoDB table name (default: companies)
- `USERS_TABLE`: DynamoDB table name (default: users)
- `AGENTS_TABLE`: DynamoDB table name (default: agents)
- `AUDIT_LOGS_TABLE`: DynamoDB table name (default: audit_logs)
- `CORS_ORIGINS`: Comma-separated allowed origins

### Frontend
- `NEXT_PUBLIC_API_URL`: Backend API URL

### Vector Database
- `VECTOR_DB_TYPE`: Database type (default: pinecone)
- `PINECONE_API_KEY`: Pinecone API key
- `PINECONE_ENVIRONMENT`: Pinecone environment
- `PINECONE_INDEX_NAME`: Pinecone index name

## API Endpoints

### Authentication
- `POST /auth/login` - Login
- `GET /auth/me` - Get current user
- `POST /auth/register` - Register user (admin only)

### Admin
- `GET /admin/companies` - List companies
- `POST /admin/companies` - Create company
- `GET /admin/companies/{id}` - Get company
- `PUT /admin/companies/{id}` - Update company
- `GET /admin/companies/{id}/users` - List company users
- `GET /admin/companies/{id}/agent` - Get agent info
- `POST /admin/companies/{id}/knowledge-base/upload` - Upload knowledge base
- `GET /admin/companies/{id}/knowledge-base/stats` - Get KB stats

### Company (Employee)
- `POST /company/chat` - Send message to agent
- `GET /company/info` - Get company info

## Troubleshooting

### Agent deployment fails
- Check AWS credentials and permissions
- Verify Secrets Manager has required keys
- Check AgentCore CLI is installed and configured

### Vector search returns no results
- Verify Pinecone index exists
- Check namespace matches company's vector_db_namespace
- Ensure knowledge base has been uploaded

### Authentication errors
- Verify JWT_SECRET_KEY is set
- Check token expiration
- Ensure user exists in database

## Next Steps

1. Set up production AWS infrastructure
2. Configure custom domains for frontend
3. Set up CI/CD pipelines
4. Add monitoring and alerting
5. Implement rate limiting
6. Add more comprehensive error handling
