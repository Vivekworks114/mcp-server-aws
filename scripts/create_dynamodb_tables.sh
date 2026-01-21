#!/bin/bash

# Script to create DynamoDB tables for Multi-Company Agent System
# Usage: ./scripts/create_dynamodb_tables.sh [region]

set -e

REGION=${1:-us-east-1}
echo "Creating DynamoDB tables in region: $REGION"

# Create Companies table
echo "Creating companies table..."
aws dynamodb create-table \
  --table-name companies \
  --attribute-definitions AttributeName=company_id,AttributeType=S \
  --key-schema AttributeName=company_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION \
  --tags Key=Environment,Value=production Key=Application,Value=multi-company-agent-system \
  > /dev/null

echo "✓ Companies table created"

# Create Users table
echo "Creating users table..."
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
  --region $REGION \
  > /dev/null

echo "✓ Users table created"

# Create Agents table
echo "Creating agents table..."
aws dynamodb create-table \
  --table-name agents \
  --attribute-definitions \
    AttributeName=agent_id,AttributeType=S \
    AttributeName=company_id,AttributeType=S \
  --key-schema AttributeName=agent_id,KeyType=HASH \
  --global-secondary-indexes \
    'IndexName=company-id-index,KeySchema=[{AttributeName=company_id,KeyType=HASH}],Projection={ProjectionType=ALL}' \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION \
  > /dev/null

echo "✓ Agents table created"

# Create Audit Logs table
echo "Creating audit_logs table..."
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
  --region $REGION \
  > /dev/null

echo "✓ Audit logs table created"

# Enable TTL on audit_logs
echo "Enabling TTL on audit_logs table..."
aws dynamodb update-time-to-live \
  --table-name audit_logs \
  --time-to-live-specification Enabled=true,AttributeName=ttl \
  --region $REGION \
  > /dev/null

echo "✓ TTL enabled on audit_logs"

# Wait for tables to be active
echo "Waiting for tables to become active..."
aws dynamodb wait table-exists --table-name companies --region $REGION
aws dynamodb wait table-exists --table-name users --region $REGION
aws dynamodb wait table-exists --table-name agents --region $REGION
aws dynamodb wait table-exists --table-name audit_logs --region $REGION

echo ""
echo "✅ All DynamoDB tables created successfully!"
echo ""
echo "Tables created:"
echo "  - companies"
echo "  - users"
echo "  - agents"
echo "  - audit_logs"
echo ""
echo "Region: $REGION"
