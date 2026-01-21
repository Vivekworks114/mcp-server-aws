"""Authentication routes"""
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import timedelta, datetime

from backend.models import LoginRequest, TokenResponse, UserCreate, UserResponse
from backend.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from backend.database import db
import uuid

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    """Login endpoint - returns JWT token"""
    # Normalize email to lowercase for lookup
    email_normalized = credentials.email.lower().strip()
    
    # Get user by email (case-insensitive)
    user = db.get_user_by_email(email_normalized)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["user_id"],
            "email": user["email"],
            "company_id": user["company_id"],
            "role": user["role"],
        },
        expires_delta=access_token_expires
    )
    
    # Log login action
    db.create_audit_log(
        user_id=user["user_id"],
        company_id=user["company_id"],
        action="login",
        details={"email": user["email"]}
    )
    
    return TokenResponse(
        access_token=access_token,
        user_id=user["user_id"],
        company_id=user["company_id"],
        role=user["role"]
    )


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, current_user: dict = Depends(get_current_user)):
    """Register a new user (admin only or self-registration for employees)"""
    # Normalize email to lowercase
    email_normalized = user_data.email.lower().strip()
    
    # Check if user already exists (case-insensitive)
    existing_user = db.get_user_by_email(email_normalized)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Verify company exists
    company = db.get_company(user_data.company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # Only admins can create users for any company
    # Employees can only create users for their own company
    if current_user.get("role") != "admin":
        if current_user.get("company_id") != user_data.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create users for your own company"
            )
    
    # Create user
    user_id = str(uuid.uuid4())
    password_hash = get_password_hash(user_data.password)
    
    user = db.create_user(
        user_id=user_id,
        email=email_normalized,  # Use normalized email
        password_hash=password_hash,
        company_id=user_data.company_id,
        role=user_data.role
    )
    
    # Log user creation
    db.create_audit_log(
        user_id=current_user["user_id"],
        company_id=user_data.company_id,
        action="user_created",
        details={"created_user_id": user_id, "email": user_data.email, "role": user_data.role}
    )
    
    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        company_id=user["company_id"],
        role=user["role"],
        created_at=datetime.fromisoformat(user["created_at"])
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        user_id=current_user["user_id"],
        email=current_user["email"],
        company_id=current_user["company_id"],
        role=current_user["role"],
        created_at=datetime.fromisoformat(current_user["created_at"])
    )
