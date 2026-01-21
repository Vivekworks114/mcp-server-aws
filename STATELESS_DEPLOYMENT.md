# Stateless Agent Deployment Guide

This document describes the production-grade stateless agent deployment system using Docker, ECR, and the Bedrock AgentCore Control API.

## Overview

The deployment system has been completely rewritten to:

- ✅ **Use Docker containers** for each company agent (Python 3.11)
- ✅ **Deploy to Amazon ECR** for container registry
- ✅ **Use boto3 Bedrock AgentCore Control API** (no CLI, no pexpect)
- ✅ **Stateless agents** (NO AgentCore memory, NO conversation persistence)
- ✅ **Company knowledge injected via system prompt/config** (not runtime memory)
- ✅ **Production-ready architecture** with proper error handling and logging

## Architecture

### Components

1. **Stateless Agent Template** (`agents/company_agent_stateless.py`)
   - No memory components (no `AgentCoreMemorySaver`, no `AgentCoreMemoryStore`)
   - No checkpointer
   - No middleware for memory persistence
   - Company knowledge injected via system prompt

2. **Dockerfile** (`agents/Dockerfile`)
   - Python 3.11 slim base image
   - Installs dependencies from `requirements.txt`
   - Copies company-specific agent code
   - Minimal runtime entry point

3. **Runtime Entry Point** (`agents/runtime.py`)
   - Minimal entry point that imports and runs the stateless agent
   - Handles Bedrock AgentCore runtime interface

4. **Deployment Function** (`backend/utils/agent_deployer.py`)
   - Generates company-specific agent code
   - Builds Docker image
   - Pushes to ECR
   - Creates agent runtime using boto3 API
   - Streams logs in real-time

## Deployment Flow

1. **Agent Code Generation**
   - Company-specific agent code is generated from template
   - Company ID, name, and vector DB namespace are injected
   - File saved as `company_agent_{company_id}_stateless.py`

2. **Docker Build**
   - Company-specific agent file is copied to `company_agent_stateless.py`
   - Docker image is built with company-specific code
   - Image is tagged with ECR URI and company ID

3. **ECR Push**
   - ECR repository is created if it doesn't exist
   - Docker image is pushed to ECR
   - Image URI format: `<account>.dkr.ecr.<region>.amazonaws.com/<repo>:<company_id>`

4. **Agent Runtime Creation**
   - Uses `bedrock-agentcore-control.create_agent_runtime` API
   - Container configuration with ECR image URI
   - Environment variables injected (API keys, company info)
   - Network mode: PUBLIC
   - IAM role for runtime execution

5. **Status Polling**
   - Polls agent runtime status until ACTIVE
   - Retrieves endpoint URL
   - Updates database with deployment info

## Key Features

### Stateless Design
- **No Memory**: Agents do not maintain conversation history
- **No State**: Each request is independent
- **Knowledge in Prompt**: Company knowledge injected via system prompt
- **Isolation**: Company data isolation via vector DB namespaces

### Production Features
- **Real-time Logging**: Deployment logs streamed to database in real-time
- **Error Handling**: Comprehensive error handling with detailed error messages
- **Retry Logic**: Automatic retries for transient failures
- **Status Tracking**: Deployment status tracked in database
- **Non-blocking**: Deployment runs in background thread pool

### Security
- **Secrets Management**: API keys stored in AWS Secrets Manager
- **IAM Roles**: Least-privilege IAM roles for runtime execution
- **Company Isolation**: Strict data isolation between companies
- **No Hardcoded Secrets**: All secrets retrieved from Secrets Manager

## Files Created/Modified

### New Files
- `agents/company_agent_stateless.py` - Stateless agent template
- `agents/Dockerfile` - Docker image definition
- `agents/runtime.py` - Minimal runtime entry point
- `DEPLOYMENT_ENV_VARS.md` - Environment variable documentation
- `STATELESS_DEPLOYMENT.md` - This file

### Modified Files
- `backend/utils/agent_deployer.py` - Complete rewrite for Docker/ECR/boto3
- `agents/agent_factory.py` - Added stateless agent generation functions

## Usage

### Prerequisites

1. **Docker** installed and running
2. **AWS Credentials** configured (via environment variables or IAM role)
3. **IAM Role** created with proper permissions (see `DEPLOYMENT_ENV_VARS.md`)
4. **Secrets** stored in AWS Secrets Manager:
   - `agentcore/groq-api-key`
   - `agentcore/huggingface-token` (optional)
   - `agentcore/pinecone-api-key` (optional)

### Environment Variables

See `DEPLOYMENT_ENV_VARS.md` for complete list of required and optional environment variables.

### Deployment

Deployment is triggered automatically when a company is created via the Admin Panel:

```python
# In backend/routes/admin.py
# Company creation triggers agent deployment in background
```

The deployment process:
1. Creates agent record in database
2. Generates company-specific agent code
3. Builds Docker image
4. Pushes to ECR
5. Creates agent runtime via boto3 API
6. Polls for ACTIVE status
7. Updates database with deployment info

## Differences from Previous Implementation

### Removed
- ❌ `agentcore configure` CLI command
- ❌ `agentcore launch` CLI command
- ❌ `pexpect` for interactive prompt handling
- ❌ AgentCore memory (long-term and short-term)
- ❌ Conversation persistence
- ❌ `.bedrock_agentcore.yaml` configuration file

### Added
- ✅ Docker containerization
- ✅ ECR image registry
- ✅ boto3 Bedrock AgentCore Control API
- ✅ Stateless agent architecture
- ✅ Real-time log streaming
- ✅ Production-grade error handling

## Troubleshooting

### Docker Build Fails
- Ensure Docker is installed and running: `docker --version`
- Check Docker daemon is running: `docker ps`
- Verify Dockerfile syntax: `docker build --dry-run`

### ECR Push Fails
- Verify AWS credentials are configured
- Check IAM permissions for ECR operations
- Ensure ECR repository exists or can be created

### Agent Runtime Creation Fails
- Verify IAM role ARN is correct
- Check IAM role has required permissions (Bedrock, CloudWatch Logs)
- Ensure ECR image URI is accessible
- Check network configuration (PUBLIC vs VPC)

### Agent Runtime Not Becoming Active
- Check CloudWatch Logs for agent runtime errors
- Verify environment variables are correctly set
- Ensure container can pull ECR image
- Check IAM role permissions

## Monitoring

### Deployment Logs
- Real-time logs stored in `agents` table `deployment_logs` field
- Viewable in Admin Panel during deployment
- Logs include Docker build output, ECR push status, API responses

### Agent Runtime Status
- Status tracked in `agents` table `deployment_status` field
- Values: `pending`, `deploying`, `active`, `failed`
- Endpoint URL stored in `agent_endpoint` field

### CloudWatch Logs
- Agent runtime logs available in CloudWatch Logs
- Log group: `/aws/bedrock/agentcore/runtime/<agent-runtime-name>`

## Next Steps

1. **Test Deployment**: Create a test company and verify deployment succeeds
2. **Monitor Logs**: Check deployment logs for any issues
3. **Verify Agent**: Test agent invocation via company panel
4. **Scale**: Deploy multiple companies and verify isolation

## Support

For issues or questions:
1. Check deployment logs in Admin Panel
2. Review CloudWatch Logs for agent runtime errors
3. Verify environment variables are set correctly
4. Check IAM role permissions
