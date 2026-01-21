"""Pydantic models for request/response validation"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class CompanyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class AgentDeploymentStatus(str, Enum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    FAILED = "failed"
    STOPPED = "stopped"


# Auth Models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    company_id: str
    role: UserRole


# Company Models
class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)
    employee_email: Optional[EmailStr] = Field(None, description="Employee email (defaults to employee@{company_name}.com)")
    employee_password: Optional[str] = Field(None, min_length=8, description="Employee password (defaults to 'password123' if not provided)")


class CompanyResponse(BaseModel):
    company_id: str
    name: str
    status: CompanyStatus
    created_at: datetime
    agent_deployment_id: Optional[str] = None
    vector_db_namespace: Optional[str] = None
    agent_status: Optional[AgentDeploymentStatus] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[CompanyStatus] = None


# User Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    company_id: str
    role: UserRole = UserRole.EMPLOYEE


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    company_id: str
    role: UserRole
    created_at: datetime


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)
    role: Optional[UserRole] = None


# Agent Models
class AgentResponse(BaseModel):
    agent_id: str
    company_id: str
    deployment_status: AgentDeploymentStatus
    memory_id: Optional[str] = None
    deployment_id: Optional[str] = None
    agent_arn: Optional[str] = None
    agent_endpoint: Optional[str] = None
    ecr_uri: Optional[str] = None
    codebuild_id: Optional[str] = None
    deployment_error: Optional[str] = None
    deployment_logs: Optional[List[str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Chat Models
class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: datetime


# Knowledge Base Models
class KnowledgeBaseUpload(BaseModel):
    company_id: str
    data: List[dict] = Field(..., description="List of FAQ entries with 'question' and 'answer' fields")


class KnowledgeBaseStats(BaseModel):
    company_id: str
    total_entries: int
    last_updated: Optional[datetime] = None


class KnowledgeBaseEntry(BaseModel):
    id: str
    question: str
    answer: str
    text: Optional[str] = None


class KnowledgeBaseListResponse(BaseModel):
    entries: List[KnowledgeBaseEntry]
    total: int


class KnowledgeBaseDeleteRequest(BaseModel):
    vector_ids: Optional[List[str]] = None  # If None, delete all


# Audit Log Models
class AuditLogEntry(BaseModel):
    log_id: str
    timestamp: datetime
    user_id: str
    company_id: str
    action: str
    details: dict


# List Response Models
class CompanyListResponse(BaseModel):
    companies: List[CompanyResponse]
    total: int


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int


class AuditLogListResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
