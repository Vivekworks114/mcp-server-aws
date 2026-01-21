# Environment Variables Setup Guide

This guide explains how to set up environment variables for each component of the multi-company agent system.

## Quick Start

1. **Backend**: Copy `backend/.env.example` to `backend/.env` and configure
2. **Admin Panel**: Copy `frontend/admin-panel/.env.example` to `frontend/admin-panel/.env.local`
3. **Company Panel**: Copy `frontend/company-panel/.env.example` to `frontend/company-panel/.env.local`
4. **Agents**: Environment variables are set automatically during deployment (see `agents/.env.example` for reference)

## Component-Specific Setup

### Backend (`backend/.env`)

Required variables:
- `JWT_SECRET_KEY`: Secret key for JWT token signing (use a long random string)
- `AWS_REGION`: AWS region (e.g., `us-east-1`)
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: AWS credentials
- `PINECONE_API_KEY`: Pinecone API key for vector database
- `GROQ_API_KEY`: Groq API key (for development/testing)
- `HF_API_KEY`: Hugging Face token (optional but recommended)

Optional variables:
- DynamoDB table names (defaults provided)
- CORS origins
- Server host/port

### Admin Panel (`frontend/admin-panel/.env.local`)

Required variables:
- `NEXT_PUBLIC_API_URL`: Backend API URL (e.g., `http://localhost:8000`)

### Company Panel (`frontend/company-panel/.env.local`)

Required variables:
- `NEXT_PUBLIC_API_URL`: Backend API URL (e.g., `http://localhost:8000`)

### Agents (`agents/.env`)

**Note**: Agent environment variables are typically set automatically during deployment via `agentcore launch`. The `.env.example` file is for reference only.

For local testing:
- `COMPANY_ID`: Company identifier
- `COMPANY_NAME`: Company name
- `MEMORY_ID`: AgentCore Memory ID
- `VECTOR_DB_NAMESPACE`: Vector database namespace
- `GROQ_API_KEY`: Groq API key
- `HF_API_KEY`: Hugging Face token
- `PINECONE_API_KEY`: Pinecone API key

## Production Setup

### AWS Secrets Manager

In production, store sensitive credentials in AWS Secrets Manager:

```bash
# Store Groq API key
aws secretsmanager create-secret \
  --name agentcore/groq-api-key \
  --secret-string "your-groq-api-key"

# Store Hugging Face token
aws secretsmanager create-secret \
  --name agentcore/huggingface-token \
  --secret-string "your-hf-token"

# Store Pinecone API key (optional)
aws secretsmanager create-secret \
  --name agentcore/pinecone-api-key \
  --secret-string "your-pinecone-key"
```

### Environment-Specific Values

#### Development
- `NEXT_PUBLIC_API_URL=http://localhost:8000`
- `CORS_ORIGINS=http://localhost:3000,http://localhost:3001`

#### Staging
- `NEXT_PUBLIC_API_URL=https://api-staging.yourdomain.com`
- `CORS_ORIGINS=https://admin-staging.yourdomain.com,https://app-staging.yourdomain.com`

#### Production
- `NEXT_PUBLIC_API_URL=https://api.yourdomain.com`
- `CORS_ORIGINS=https://admin.yourdomain.com,https://app.yourdomain.com`

## Security Best Practices

1. **Never commit `.env` files** - They are in `.gitignore`
2. **Use strong JWT secrets** - Generate with: `openssl rand -hex 32`
3. **Rotate credentials regularly** - Especially API keys
4. **Use AWS Secrets Manager in production** - Don't hardcode secrets
5. **Limit CORS origins** - Only include trusted domains
6. **Use different secrets per environment** - Dev, staging, production should have different keys

## Troubleshooting

### Backend can't connect to DynamoDB
- Check `AWS_REGION` is correct
- Verify AWS credentials are configured
- Ensure IAM permissions allow DynamoDB access

### Frontend can't connect to backend
- Verify `NEXT_PUBLIC_API_URL` is correct
- Check CORS configuration in backend
- Ensure backend is running

### Agents can't access vector database
- Verify `PINECONE_API_KEY` is set
- Check `PINECONE_INDEX_NAME` exists
- Ensure namespace matches company's `vector_db_namespace`

### Authentication fails
- Verify `JWT_SECRET_KEY` is set and consistent
- Check token expiration settings
- Ensure user exists in database
