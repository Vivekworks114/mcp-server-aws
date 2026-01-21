"""DynamoDB database operations"""
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from backend.models import (
    CompanyStatus,
    AgentDeploymentStatus,
    UserRole,
    CompanyResponse,
    UserResponse,
    AgentResponse,
    AuditLogEntry,
)


class DynamoDBClient:
    """DynamoDB client wrapper for table operations"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        self.companies_table = self.dynamodb.Table(os.getenv('COMPANIES_TABLE', 'companies'))
        self.users_table = self.dynamodb.Table(os.getenv('USERS_TABLE', 'users'))
        self.agents_table = self.dynamodb.Table(os.getenv('AGENTS_TABLE', 'agents'))
        self.audit_logs_table = self.dynamodb.Table(os.getenv('AUDIT_LOGS_TABLE', 'audit_logs'))
    
    # Company Operations
    def create_company(self, company_id: str, name: str, vector_db_namespace: str) -> Dict[str, Any]:
        """Create a new company record"""
        item = {
            'company_id': company_id,
            'name': name,
            'status': CompanyStatus.ACTIVE.value,
            'created_at': datetime.utcnow().isoformat(),
            'vector_db_namespace': vector_db_namespace,
        }
        self.companies_table.put_item(Item=item)
        return item
    
    def get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Get company by ID"""
        try:
            response = self.companies_table.get_item(Key={'company_id': company_id})
            return response.get('Item')
        except ClientError:
            return None
    
    def update_company(self, company_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update company fields"""
        update_expression = "SET " + ", ".join([f"{k} = :{k}" for k in updates.keys()])
        expression_values = {f":{k}": v for k, v in updates.items()}
        
        response = self.companies_table.update_item(
            Key={'company_id': company_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )
        return response['Attributes']
    
    def list_companies(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all companies"""
        response = self.companies_table.scan(Limit=limit)
        return response.get('Items', [])
    
    def delete_company(self, company_id: str) -> bool:
        """Delete a company record"""
        try:
            self.companies_table.delete_item(Key={'company_id': company_id})
            return True
        except ClientError:
            return False
    
    def update_company_agent(self, company_id: str, agent_deployment_id: str, agent_status: str):
        """Update company's agent deployment info"""
        self.update_company(company_id, {
            'agent_deployment_id': agent_deployment_id,
            'agent_status': agent_status,
        })
    
    # User Operations
    def create_user(self, user_id: str, email: str, password_hash: str, company_id: str, role: UserRole) -> Dict[str, Any]:
        """Create a new user (email is normalized to lowercase)"""
        item = {
            'user_id': user_id,
            'email': email.lower().strip(),  # Normalize email to lowercase
            'password_hash': password_hash,
            'company_id': company_id,
            'role': role.value,
            'created_at': datetime.utcnow().isoformat(),
        }
        self.users_table.put_item(Item=item)
        return item
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            response = self.users_table.get_item(Key={'user_id': user_id})
            return response.get('Item')
        except ClientError:
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email (case-insensitive lookup)"""
        try:
            # Normalize email to lowercase for lookup
            email_lower = email.lower().strip()
            
            # Scan and filter (case-insensitive comparison)
            response = self.users_table.scan(
                Limit=1000  # Increase limit to scan more records
            )
            items = response.get('Items', [])
            
            # Find matching email (case-insensitive)
            for item in items:
                if item.get('email', '').lower().strip() == email_lower:
                    return item
            
            return None
        except ClientError:
            return None
    
    def get_users_by_company(self, company_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all users for a company"""
        try:
            response = self.users_table.scan(
                FilterExpression=Attr('company_id').eq(company_id),
                Limit=limit
            )
            return response.get('Items', [])
        except ClientError:
            return []
    
    def delete_users_by_company(self, company_id: str) -> int:
        """Delete all users for a company"""
        try:
            # Get all users for the company
            users = self.get_users_by_company(company_id, limit=1000)
            deleted_count = 0
            
            # Delete each user
            for user in users:
                try:
                    self.users_table.delete_item(Key={'user_id': user['user_id']})
                    deleted_count += 1
                except ClientError:
                    pass  # Continue even if one deletion fails
            
            return deleted_count
        except ClientError:
            return 0
    
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update user fields"""
        update_expression = "SET " + ", ".join([f"{k} = :{k}" for k in updates.keys()])
        expression_values = {f":{k}": v for k, v in updates.items()}
        
        response = self.users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )
        return response['Attributes']
    
    # Agent Operations
    def create_agent(self, agent_id: str, company_id: str, memory_id: str) -> Dict[str, Any]:
        """Create agent record"""
        item = {
            'agent_id': agent_id,
            'company_id': company_id,
            'deployment_status': AgentDeploymentStatus.PENDING.value,
            'memory_id': memory_id,
            'created_at': datetime.utcnow().isoformat(),
        }
        self.agents_table.put_item(Item=item)
        return item
    
    def get_agent_by_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Get agent for a company"""
        try:
            # Note: Scan operations use eventual consistency, so there may be a brief delay
            # after creating an agent before it's visible in scan results
            response = self.agents_table.scan(
                FilterExpression=Attr('company_id').eq(company_id),
                Limit=1
            )
            items = response.get('Items', [])
            return items[0] if items else None
        except ClientError as e:
            # Log the error for debugging
            import logging
            logging.error(f"Error getting agent by company_id {company_id}: {str(e)}")
            return None
    
    def update_agent(self, agent_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update agent fields"""
        updates['updated_at'] = datetime.utcnow().isoformat()
        update_expression = "SET " + ", ".join([f"{k} = :{k}" for k in updates.keys()])
        expression_values = {f":{k}": v for k, v in updates.items()}
        
        response = self.agents_table.update_item(
            Key={'agent_id': agent_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )
        return response['Attributes']
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent record"""
        try:
            self.agents_table.delete_item(Key={'agent_id': agent_id})
            return True
        except ClientError:
            return False
    
    def get_agent_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent by ID"""
        try:
            response = self.agents_table.get_item(Key={'agent_id': agent_id})
            return response.get('Item')
        except ClientError:
            return None
    
    # Audit Log Operations
    def create_audit_log(self, user_id: str, company_id: str, action: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create audit log entry"""
        log_id = str(uuid.uuid4())
        item = {
            'log_id': log_id,
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'company_id': company_id,
            'action': action,
            'details': details,
        }
        self.audit_logs_table.put_item(Item=item)
        return item
    
    def get_audit_logs_by_company(self, company_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit logs for a company"""
        try:
            response = self.audit_logs_table.scan(
                FilterExpression=Attr('company_id').eq(company_id),
                Limit=limit
            )
            return sorted(response.get('Items', []), key=lambda x: x['timestamp'], reverse=True)
        except ClientError:
            return []
    
    def get_audit_logs_by_user(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit logs for a user"""
        try:
            response = self.audit_logs_table.scan(
                FilterExpression=Attr('user_id').eq(user_id),
                Limit=limit
            )
            return sorted(response.get('Items', []), key=lambda x: x['timestamp'], reverse=True)
        except ClientError:
            return []
    
    def delete_audit_logs_by_company(self, company_id: str) -> int:
        """Delete all audit logs for a company"""
        try:
            # Get all audit logs for the company
            logs = self.get_audit_logs_by_company(company_id, limit=10000)
            deleted_count = 0
            
            # Delete each log
            for log in logs:
                try:
                    self.audit_logs_table.delete_item(Key={'log_id': log['log_id']})
                    deleted_count += 1
                except ClientError:
                    pass  # Continue even if one deletion fails
            
            return deleted_count
        except ClientError:
            return 0


# Singleton instance
db = DynamoDBClient()
