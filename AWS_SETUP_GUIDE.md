# AWS Setup Guide for Multi-Company Agent System

This guide provides step-by-step instructions for setting up all AWS resources required for the multi-company agent system.

## Prerequisites

- AWS Account with admin access
- AWS CLI installed and configured
- Python 3.13+ installed
- AgentCore CLI installed (`pip install bedrock-agentcore-starter-toolkit`)

## Step 1: Configure AWS CLI

```bash
# Install AWS CLI if not already installed
# macOS: brew install awscli
# Linux: pip install awscli
# Windows: Download from AWS website

# Configure AWS credentials
aws configure

# Enter your:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (e.g., us-east-1)
# - Default output format (json)
```

## Step 2: Enable Required AWS Services

### 2.1 Enable Amazon Bedrock AgentCore

1. Go to [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Navigate to **AgentCore** in the left sidebar
3. Click **Get Started** or **Enable AgentCore**
4. Accept the terms and conditions
5. Wait for the service to be enabled (may take a few minutes)

**Note**: AgentCore is available in specific regions:
- `us-east-1` (N. Virginia)
- `us-west-2` (Oregon)
- `ap-southeast-2` (Sydney)
- `eu-west-1` (Ireland)

### 2.2 Verify Bedrock Access

```bash
# Test Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

## Step 3: Create DynamoDB Tables

### Option A: Using AWS CLI (Recommended)

```bash
# Set your region
export AWS_REGION=us-east-1

# Create Companies table
aws dynamodb create-table \
  --table-name companies \
  --attribute-definitions AttributeName=company_id,AttributeType=S \
  --key-schema AttributeName=company_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION

# Create Users table with GSI
aws dynamodb create-table \
  --table-name users \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=company_id,AttributeType=S \
    AttributeName=email,AttributeType=S \
  --key-schema AttributeName=user_id,KeyType=HASH \
  --global-secondary-indexes \
    'IndexName=company-id-index,KeySchema=[{AttributeName=company_id,KeyType=HASH}],Projection={ProjectionType=ALL}' \
    'IndexName=email-index,KeySchema=[{AttributeName=email,KeyType=HASH}],Projection={ProjectionType=ALL}' \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION

# Create Agents table with GSI
aws dynamodb create-table \
  --table-name agents \
  --attribute-definitions \
    AttributeName=agent_id,AttributeType=S \
    AttributeName=company_id,AttributeType=S \
  --key-schema AttributeName=agent_id,KeyType=HASH \
  --global-secondary-indexes \
    'IndexName=company-id-index,KeySchema=[{AttributeName=company_id,KeyType=HASH}],Projection={ProjectionType=ALL}' \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION

# Create Audit Logs table with GSI and TTL
aws dynamodb create-table \
  --table-name audit_logs \
  --attribute-definitions \
    AttributeName=log_id,AttributeType=S \
    AttributeName=timestamp,AttributeType=S \
    AttributeName=company_id,AttributeType=S \
    AttributeName=user_id,AttributeType=S \
  --key-schema \
    AttributeName=log_id,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --global-secondary-indexes \
    'IndexName=company-id-index,KeySchema=[{AttributeName=company_id,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
    'IndexName=user-id-index,KeySchema=[{AttributeName=user_id,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
  --billing-mode PAY_PER_REQUEST \
  --region $AWS_REGION

# Enable TTL on audit_logs table
aws dynamodb update-time-to-live \
  --table-name audit_logs \
  --time-to-live-specification Enabled=true,AttributeName=ttl \
  --region $AWS_REGION
```

### Option B: Using AWS Console

1. Go to [DynamoDB Console](https://console.aws.amazon.com/dynamodb/)
2. Click **Create table**
3. For each table, use the configuration from `infrastructure/dynamodb_tables.json`
4. Repeat for all 4 tables: `companies`, `users`, `agents`, `audit_logs`

### Verify Tables Created

```bash
# List all tables
aws dynamodb list-tables --region $AWS_REGION

# Verify a table exists
aws dynamodb describe-table --table-name companies --region $AWS_REGION
```

## Step 4: Store Secrets in AWS Secrets Manager

### 4.1 Create Secrets

```bash
# Store Groq API Key
aws secretsmanager create-secret \
  --name agentcore/groq-api-key \
  --secret-string "your-actual-groq-api-key-here" \
  --description "Groq API key for LLM service" \
  --region $AWS_REGION

# Store Hugging Face Token
aws secretsmanager create-secret \
  --name agentcore/huggingface-token \
  --secret-string "your-actual-hf-token-here" \
  --description "Hugging Face API token for embeddings" \
  --region $AWS_REGION

# Store Pinecone API Key (optional but recommended)
aws secretsmanager create-secret \
  --name agentcore/pinecone-api-key \
  --secret-string "your-actual-pinecone-api-key-here" \
  --description "Pinecone API key for vector database" \
  --region $AWS_REGION
```

### 4.2 Verify Secrets

```bash
# List secrets
aws secretsmanager list-secrets --region $AWS_REGION --query "SecretList[?contains(Name, 'agentcore')]"

# Test retrieving a secret (replace with your actual secret name)
aws secretsmanager get-secret-value \
  --secret-id agentcore/groq-api-key \
  --region $AWS_REGION \
  --query SecretString \
  --output text
```

## Step 5: Create IAM Role for Backend Service

### 5.1 Create IAM Policy

Create a file `backend-iam-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/companies",
        "arn:aws:dynamodb:*:*:table/users",
        "arn:aws:dynamodb:*:*:table/agents",
        "arn:aws:dynamodb:*:*:table/audit_logs",
        "arn:aws:dynamodb:*:*:table/companies/index/*",
        "arn:aws:dynamodb:*:*:table/users/index/*",
        "arn:aws:dynamodb:*:*:table/agents/index/*",
        "arn:aws:dynamodb:*:*:table/audit_logs/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:agentcore/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeAgent",
        "bedrock-runtime:InvokeAgent"
      ],
      "Resource": "*"
    }
  ]
}
```

### 5.2 Create IAM Policy

```bash
aws iam create-policy \
  --policy-name MultiCompanyAgentBackendPolicy \
  --policy-document file://backend-iam-policy.json \
  --description "Policy for backend service to access DynamoDB, Secrets Manager, and Bedrock"
```

### 5.3 Create IAM Role (for ECS/Lambda/App Runner)

```bash
# Create trust policy file trust-policy.json
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name MultiCompanyAgentBackendRole \
  --assume-role-policy-document file://trust-policy.json \
  --description "Role for backend service"

# Attach policy to role
aws iam attach-role-policy \
  --role-name MultiCompanyAgentBackendRole \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/MultiCompanyAgentBackendPolicy

# Replace YOUR_ACCOUNT_ID with your actual AWS account ID
# Get account ID: aws sts get-caller-identity --query Account --output text
```

## Step 6: Configure AgentCore CLI

### 6.1 Install AgentCore CLI

```bash
pip install bedrock-agentcore-starter-toolkit
```

### 6.2 Configure AgentCore

```bash
# Initialize AgentCore (if needed)
agentcore configure

# Verify configuration
agentcore --version
```

## Step 7: Test AWS Setup

### 7.1 Test DynamoDB Access

```python
# Create test script: test_aws_setup.py
import boto3
import os

os.environ['AWS_REGION'] = 'us-east-1'

# Test DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('companies')
print(f"Table status: {table.table_status}")

# Test Secrets Manager
secrets = boto3.client('secretsmanager')
try:
    secret = secrets.get_secret_value(SecretId='agentcore/groq-api-key')
    print("✓ Secrets Manager access working")
except Exception as e:
    print(f"✗ Secrets Manager error: {e}")

# Test Bedrock
bedrock = boto3.client('bedrock', region_name='us-east-1')
try:
    models = bedrock.list_foundation_models()
    print("✓ Bedrock access working")
except Exception as e:
    print(f"✗ Bedrock error: {e}")
```

```bash
python test_aws_setup.py
```

## Step 8: Environment Variables for Backend

Update your `backend/.env` file:

```bash
# Copy example file
cp backend/env.example backend/.env

# Edit with your values
# JWT_SECRET_KEY=generate-with: openssl rand -hex 32
# AWS_REGION=us-east-1
# PINECONE_API_KEY=your-key
# etc.
```

## Step 9: Deploy Backend (Choose One Option)

### Option A: Local Development

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Option B: AWS App Runner

1. Create `Dockerfile` in backend directory
2. Push to ECR or GitHub
3. Create App Runner service in AWS Console
4. Configure environment variables
5. Attach IAM role created in Step 5

### Option C: AWS ECS (Fargate)

1. Create ECS cluster
2. Create task definition with IAM role
3. Create service
4. Configure load balancer

### Option D: AWS Lambda

1. Package backend as Lambda function
2. Create Lambda function
3. Configure API Gateway
4. Set environment variables
5. Attach IAM role

## Step 10: Verify Complete Setup

### 10.1 Check All Resources

```bash
# Verify DynamoDB tables
aws dynamodb list-tables --region us-east-1

# Verify Secrets
aws secretsmanager list-secrets --region us-east-1 --query "SecretList[?contains(Name, 'agentcore')].Name"

# Verify IAM role
aws iam get-role --role-name MultiCompanyAgentBackendRole

# Verify Bedrock AgentCore access
aws bedrock-agent list-agents --region us-east-1
```

### 10.2 Test Backend Connection

```bash
# Start backend locally
cd backend
uvicorn main:app --reload

# In another terminal, test health endpoint
curl http://localhost:8000/health

# Should return: {"status": "healthy"}
```

## Step 11: Production Considerations

### 11.1 Enable CloudWatch Logs

```bash
# Create CloudWatch log group
aws logs create-log-group \
  --log-group-name /aws/multi-company-agent/backend \
  --region $AWS_REGION
```

### 11.2 Set Up CloudWatch Alarms

- Monitor DynamoDB throttling
- Monitor API errors
- Monitor agent deployment failures

### 11.3 Enable AWS WAF (Optional)

For API Gateway or CloudFront:
- Rate limiting
- IP filtering
- DDoS protection

### 11.4 Backup Strategy

- Enable DynamoDB point-in-time recovery
- Regular backups of Secrets Manager
- Export audit logs to S3

## Troubleshooting

### Issue: "Access Denied" errors

**Solution**: Check IAM permissions and ensure role is attached correctly.

### Issue: DynamoDB table not found

**Solution**: Verify table name matches exactly and region is correct.

### Issue: Secrets Manager access denied

**Solution**: Ensure IAM policy includes `secretsmanager:GetSecretValue` for the secret ARN.

### Issue: Bedrock AgentCore not available

**Solution**: 
- Verify region supports AgentCore
- Check service is enabled in your account
- Wait for service activation (can take 10-15 minutes)

### Issue: Agent deployment fails

**Solution**:
- Verify AgentCore CLI is configured
- Check AWS credentials have Bedrock permissions
- Ensure secrets are accessible

## Quick Reference Commands

```bash
# Get AWS Account ID
aws sts get-caller-identity --query Account --output text

# List all DynamoDB tables
aws dynamodb list-tables --region us-east-1

# Get secret value
aws secretsmanager get-secret-value --secret-id agentcore/groq-api-key --region us-east-1

# Check table status
aws dynamodb describe-table --table-name companies --region us-east-1

# List IAM roles
aws iam list-roles --query "Roles[?contains(RoleName, 'MultiCompany')].RoleName"

# Test Bedrock access
aws bedrock list-foundation-models --region us-east-1 --max-results 5
```

## Next Steps

After completing AWS setup:

1. ✅ Configure backend environment variables
2. ✅ Start backend service
3. ✅ Set up frontend applications
4. ✅ Create first company via Admin Panel
5. ✅ Verify agent deployment
6. ✅ Test end-to-end flow

For detailed deployment instructions, see `README_IMPLEMENTATION.md`.
