# AWS Setup Checklist

Use this checklist to track your AWS setup progress.

## Prerequisites
- [ ] AWS Account created
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS CLI configured (`aws configure`)
- [ ] Python 3.13+ installed
- [ ] AgentCore CLI installed (`pip install bedrock-agentcore-starter-toolkit`)

## Step 1: Enable AWS Services
- [ ] Amazon Bedrock AgentCore enabled in AWS Console
- [ ] Verified Bedrock access: `aws bedrock list-foundation-models --region us-east-1`

## Step 2: Create DynamoDB Tables
- [ ] Companies table created
- [ ] Users table created (with GSI)
- [ ] Agents table created (with GSI)
- [ ] Audit logs table created (with GSI and TTL)
- [ ] Verified all tables: `aws dynamodb list-tables`

**Quick Setup**: Run `./scripts/create_dynamodb_tables.sh us-east-1`

## Step 3: Store Secrets in AWS Secrets Manager
- [ ] Groq API key stored: `agentcore/groq-api-key`
- [ ] Hugging Face token stored: `agentcore/huggingface-token`
- [ ] Pinecone API key stored: `agentcore/pinecone-api-key`
- [ ] Verified secrets: `aws secretsmanager list-secrets`

**Quick Setup**: Run `./scripts/setup_secrets.sh us-east-1`

## Step 4: Create IAM Role and Policy
- [ ] IAM policy created: `MultiCompanyAgentBackendPolicy`
- [ ] IAM role created: `MultiCompanyAgentBackendRole`
- [ ] Policy attached to role
- [ ] Trust policy configured (for ECS/Lambda/App Runner)

## Step 5: Configure Backend Environment
- [ ] Copied `backend/env.example` to `backend/.env`
- [ ] Set `JWT_SECRET_KEY` (generate with: `openssl rand -hex 32`)
- [ ] Set `AWS_REGION`
- [ ] Set `PINECONE_API_KEY`
- [ ] Set other required variables

## Step 6: Test AWS Setup
- [ ] DynamoDB access working
- [ ] Secrets Manager access working
- [ ] Bedrock access working
- [ ] Backend can connect to all services

## Step 7: Deploy Backend
Choose one deployment option:
- [ ] **Option A**: Local development (for testing)
- [ ] **Option B**: AWS App Runner
- [ ] **Option C**: AWS ECS (Fargate)
- [ ] **Option D**: AWS Lambda + API Gateway

## Step 8: Configure Frontend
- [ ] Admin Panel: Copied `frontend/admin-panel/env.example` to `.env.local`
- [ ] Company Panel: Copied `frontend/company-panel/env.example` to `.env.local`
- [ ] Set `NEXT_PUBLIC_API_URL` in both frontends

## Step 9: Verify Complete Setup
- [ ] Backend health check: `curl http://localhost:8000/health`
- [ ] Admin Panel loads correctly
- [ ] Company Panel loads correctly
- [ ] Can create company via Admin Panel
- [ ] Agent deploys successfully
- [ ] Can chat with agent via Company Panel

## Quick Commands Reference

```bash
# Get AWS Account ID
aws sts get-caller-identity --query Account --output text

# List DynamoDB tables
aws dynamodb list-tables --region us-east-1

# List secrets
aws secretsmanager list-secrets --region us-east-1 --query "SecretList[?contains(Name, 'agentcore')].Name"

# Get secret value
aws secretsmanager get-secret-value --secret-id agentcore/groq-api-key --region us-east-1

# Test Bedrock
aws bedrock list-foundation-models --region us-east-1 --max-results 5
```

## Troubleshooting

If any step fails, check:
1. AWS credentials are correct: `aws sts get-caller-identity`
2. Region is correct (AgentCore available regions: us-east-1, us-west-2, ap-southeast-2, eu-west-1)
3. IAM permissions are sufficient
4. Service is enabled in your account

For detailed instructions, see `AWS_SETUP_GUIDE.md`.
