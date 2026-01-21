#!/bin/bash

# Script to create/update IAM role for Bedrock AgentCore Runtime
# This role is used by the agent runtime containers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ROLE_NAME="${AGENTCORE_IAM_ROLE_NAME:-AgentCoreServiceRole}"
REGION="${AWS_REGION:-us-east-1}"

echo -e "${GREEN}Setting up IAM role for Bedrock AgentCore Runtime${NC}"
echo "Role name: $ROLE_NAME"
echo "Region: $REGION"
echo ""

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}Error: Could not get AWS account ID. Is AWS CLI configured?${NC}"
    exit 1
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo "Account ID: $ACCOUNT_ID"
echo "Role ARN: $ROLE_ARN"
echo ""

# Create trust policy file
# Note: Service principal must be bedrock-agentcore.amazonaws.com (not bedrock.amazonaws.com)
TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AssumeRolePolicy",
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock-agentcore.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "${ACCOUNT_ID}"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:*"
        }
      }
    }
  ]
}
EOF
)

# Create permissions policy
PERMISSIONS_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
        "arn:aws:bedrock:*::foundation-model/amazon.titan-*",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:${ACCOUNT_ID}:secret:agentcore/*"
      ]
    }
  ]
}
EOF
)

# Check if role exists
if aws iam get-role --role-name "$ROLE_NAME" > /dev/null 2>&1; then
    echo -e "${YELLOW}Role $ROLE_NAME already exists. Updating trust policy and permissions...${NC}"
    
    # Update trust policy
    echo "$TRUST_POLICY" > /tmp/trust-policy.json
    aws iam update-assume-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-document file:///tmp/trust-policy.json
    
    echo -e "${GREEN}✓ Trust policy updated${NC}"
    
    # Check if policy exists
    POLICY_NAME="${ROLE_NAME}Policy"
    POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
    
    if aws iam get-policy --policy-arn "$POLICY_ARN" > /dev/null 2>&1; then
        echo -e "${YELLOW}Policy $POLICY_NAME exists. Creating new version...${NC}"
        # Create new policy version
        echo "$PERMISSIONS_POLICY" > /tmp/permissions-policy.json
        aws iam create-policy-version \
            --policy-arn "$POLICY_ARN" \
            --policy-document file:///tmp/permissions-policy.json \
            --set-as-default
        echo -e "${GREEN}✓ Policy updated${NC}"
    else
        echo -e "${YELLOW}Policy $POLICY_NAME does not exist. Creating...${NC}"
        echo "$PERMISSIONS_POLICY" > /tmp/permissions-policy.json
        aws iam create-policy \
            --policy-name "$POLICY_NAME" \
            --policy-document file:///tmp/permissions-policy.json \
            --description "Permissions for Bedrock AgentCore Runtime"
        echo -e "${GREEN}✓ Policy created${NC}"
        
        # Attach policy to role
        aws iam attach-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-arn "$POLICY_ARN"
        echo -e "${GREEN}✓ Policy attached to role${NC}"
    fi
else
    echo -e "${YELLOW}Role $ROLE_NAME does not exist. Creating...${NC}"
    
    # Create role with trust policy
    echo "$TRUST_POLICY" > /tmp/trust-policy.json
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/trust-policy.json \
        --description "IAM role for Bedrock AgentCore Runtime execution"
    
    echo -e "${GREEN}✓ Role created${NC}"
    
    # Create and attach permissions policy
    POLICY_NAME="${ROLE_NAME}Policy"
    echo "$PERMISSIONS_POLICY" > /tmp/permissions-policy.json
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file:///tmp/permissions-policy.json \
        --description "Permissions for Bedrock AgentCore Runtime"
    
    POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
    echo -e "${GREEN}✓ Policy created${NC}"
    
    # Attach policy to role
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "$POLICY_ARN"
    
    echo -e "${GREEN}✓ Policy attached to role${NC}"
fi

# Clean up temp files
rm -f /tmp/trust-policy.json /tmp/permissions-policy.json

echo ""
echo -e "${GREEN}✓ IAM role setup complete!${NC}"
echo ""
echo "Role ARN: $ROLE_ARN"
echo ""
echo "Update your environment variable:"
echo "  export AGENTCORE_IAM_ROLE_ARN=\"$ROLE_ARN\""
echo ""
echo "Or add to your .env file:"
echo "  AGENTCORE_IAM_ROLE_ARN=$ROLE_ARN"
echo ""
