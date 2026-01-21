#!/bin/bash

# Script to set up AWS Secrets Manager secrets
# Usage: ./scripts/setup_secrets.sh [region]

set -e

REGION=${1:-us-east-1}
echo "Setting up secrets in region: $REGION"

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2
    local description=$3
    
    # Check if secret exists
    if aws secretsmanager describe-secret --secret-id "$secret_name" --region $REGION > /dev/null 2>&1; then
        echo "Updating existing secret: $secret_name"
        aws secretsmanager update-secret \
            --secret-id "$secret_name" \
            --secret-string "$secret_value" \
            --description "$description" \
            --region $REGION \
            > /dev/null
        echo "✓ Updated: $secret_name"
    else
        echo "Creating new secret: $secret_name"
        aws secretsmanager create-secret \
            --name "$secret_name" \
            --secret-string "$secret_value" \
            --description "$description" \
            --region $REGION \
            > /dev/null
        echo "✓ Created: $secret_name"
    fi
}

# Prompt for secrets if not provided as environment variables
if [ -z "$GROQ_API_KEY" ]; then
    read -sp "Enter Groq API Key: " GROQ_API_KEY
    echo ""
fi

if [ -z "$HF_API_KEY" ]; then
    read -sp "Enter Hugging Face API Token: " HF_API_KEY
    echo ""
fi

if [ -z "$PINECONE_API_KEY" ]; then
    read -sp "Enter Pinecone API Key: " PINECONE_API_KEY
    echo ""
fi

# Create secrets
create_or_update_secret \
    "agentcore/groq-api-key" \
    "$GROQ_API_KEY" \
    "Groq API key for LLM service"

create_or_update_secret \
    "agentcore/huggingface-token" \
    "$HF_API_KEY" \
    "Hugging Face API token for embeddings"

create_or_update_secret \
    "agentcore/pinecone-api-key" \
    "$PINECONE_API_KEY" \
    "Pinecone API key for vector database"

echo ""
echo "✅ All secrets created/updated successfully!"
echo ""
echo "Secrets created:"
echo "  - agentcore/groq-api-key"
echo "  - agentcore/huggingface-token"
echo "  - agentcore/pinecone-api-key"
echo ""
echo "Region: $REGION"
echo ""
echo "To retrieve a secret:"
echo "  aws secretsmanager get-secret-value --secret-id agentcore/groq-api-key --region $REGION"
