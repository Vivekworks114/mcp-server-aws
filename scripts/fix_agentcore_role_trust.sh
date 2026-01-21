#!/bin/bash

# Quick script to fix the trust policy for existing AgentCoreServiceRole
# This updates the trust policy to use the correct service principal

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ROLE_NAME="${AGENTCORE_IAM_ROLE_NAME:-AgentCoreServiceRole}"
REGION="${AWS_REGION:-us-east-1}"

echo -e "${GREEN}Fixing trust policy for AgentCoreServiceRole${NC}"
echo "Role name: $ROLE_NAME"
echo "Region: $REGION"
echo ""

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${YELLOW}Warning: Could not get AWS account ID. Using placeholder.${NC}"
    echo "Please set ACCOUNT_ID environment variable or ensure AWS CLI is configured."
    read -p "Enter your AWS Account ID: " ACCOUNT_ID
fi

echo "Account ID: $ACCOUNT_ID"
echo ""

# Create correct trust policy
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

# Save to temp file
echo "$TRUST_POLICY" > /tmp/trust-policy.json

# Update trust policy
echo -e "${YELLOW}Updating trust policy...${NC}"
aws iam update-assume-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-document file:///tmp/trust-policy.json

echo -e "${GREEN}✓ Trust policy updated successfully!${NC}"
echo ""
echo "The trust policy now allows bedrock-agentcore.amazonaws.com to assume the role."
echo ""

# Clean up
rm -f /tmp/trust-policy.json

# Verify
echo "Verifying trust policy..."
aws iam get-role --role-name "$ROLE_NAME" --query 'Role.AssumeRolePolicyDocument' --output json | python3 -m json.tool

echo ""
echo -e "${GREEN}Done! Try deploying your agent again.${NC}"
