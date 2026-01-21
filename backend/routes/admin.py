"""Admin routes for company and user management"""
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from typing import List
from datetime import datetime
import uuid

from backend.models import (
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    CompanyListResponse,
    UserResponse,
    UserListResponse,
    UserUpdate,
    AgentResponse,
    AuditLogEntry,
    AuditLogListResponse,
    KnowledgeBaseUpload,
    KnowledgeBaseStats,
    KnowledgeBaseEntry,
    KnowledgeBaseListResponse,
    KnowledgeBaseDeleteRequest,
)
from backend.auth import get_current_admin_user, verify_company_access
from backend.database import db
from backend.utils.agent_deployer import deploy_company_agent
from backend.utils.vector_db import VectorDBClient
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
try:
    from langchain_openai import OpenAIEmbeddings
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_admin_user)
):
    """Create a new company and automatically deploy its agent"""
    # Check if company name already exists
    existing_companies = db.list_companies()
    for company in existing_companies:
        if company.get("name") == company_data.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company name already exists"
            )
    
    # Generate company ID and namespace
    company_id = str(uuid.uuid4())
    vector_db_namespace = f"company_{company_id}"
    
    # Create company record
    company = db.create_company(
        company_id=company_id,
        name=company_data.name,
        vector_db_namespace=vector_db_namespace
    )
    
    # Create initial admin user
    from backend.auth import get_password_hash
    from backend.models import UserRole
    admin_user_id = str(uuid.uuid4())
    # Normalize admin email to lowercase
    admin_email_normalized = company_data.admin_email.lower().strip()
    admin_user = db.create_user(
        user_id=admin_user_id,
        email=admin_email_normalized,
        password_hash=get_password_hash(company_data.admin_password),
        company_id=company_id,
        role=UserRole.ADMIN
    )
    
    # Create employee user for company access
    # Generate default employee email if not provided
    employee_email = company_data.employee_email
    if not employee_email:
        # Create email from company name (sanitized)
        company_name_safe = "".join(c if c.isalnum() else "" for c in company_data.name.lower())[:20]
        employee_email = f"employee@{company_name_safe}.com"
        # Ensure uniqueness by appending company_id suffix if needed
        if len(company_name_safe) < 3:
            employee_email = f"employee@{company_id[:8]}.com"
    
    # Normalize email to lowercase (database.create_user will also normalize, but do it here too)
    employee_email = employee_email.lower().strip()
    
    # Generate default password if not provided
    employee_password = company_data.employee_password or "password123"
    
    employee_user_id = str(uuid.uuid4())
    employee_user = db.create_user(
        user_id=employee_user_id,
        email=employee_email,
        password_hash=get_password_hash(employee_password),
        company_id=company_id,
        role=UserRole.EMPLOYEE
    )
    
    # Initialize vector database namespace
    vector_db = VectorDBClient()
    vector_db.create_namespace(vector_db_namespace)
    
    # Create agent record immediately (before background task starts)
    # This ensures the frontend can poll for agent status right away
    from backend.models import AgentDeploymentStatus
    agent_id = str(uuid.uuid4())
    # Stateless agents - no memory required
    memory_id = None
    
    try:
        # Create agent record (stateless - no memory)
        db.create_agent(
            agent_id=agent_id,
            company_id=company_id,
            memory_id=memory_id
        )
        
        # Set initial status and logs
        db.update_agent(agent_id, {
            "deployment_status": AgentDeploymentStatus.PENDING.value,
            "deployment_logs": [f"[{datetime.utcnow().isoformat()}] Agent deployment queued"]
        })
        
        # Verify agent was created and can be retrieved
        created_agent = db.get_agent_by_id(agent_id)
        if not created_agent:
            raise Exception(f"Agent record created but not retrievable for company {company_id}")
        
        # Also verify by company_id (the method used by the endpoint)
        agent_by_company = db.get_agent_by_company(company_id)
        if not agent_by_company:
            # Log warning but continue - might be eventual consistency
            import logging
            logging.warning(f"Agent created but not immediately retrievable by company_id: {company_id}")
        
    except Exception as e:
        # Log error but don't fail company creation
        import logging
        logging.error(f"Error creating agent record: {str(e)}")
        # Still create company, but agent will be created during deployment
        agent_id = None
        memory_id = None
    
    # Update company agent status and store agent_id in company record
    if agent_id:
        db.update_company_agent(company_id, None, AgentDeploymentStatus.PENDING.value)
        # Also store agent_id in company record for direct lookup (strongly consistent)
        db.update_company(company_id, {"agent_id": agent_id})
    
    # Deploy agent in background (non-blocking)
    async def deploy_agent_background():
        """Background task to deploy agent"""
        if not agent_id:
            # Agent record creation failed, create it during deployment
            import logging
            logging.warning(f"Agent record not created initially, will be created during deployment for company {company_id}")
            try:
                await deploy_company_agent(company_id, company_data.name, agent_id=None)
            except Exception as e:
                error_msg = str(e)
                db.create_audit_log(
                    user_id=current_user["user_id"],
                    company_id=company_id,
                    action="agent_deployment_failed",
                    details={"error": error_msg}
                )
                db.update_company_agent(company_id, None, "failed")
            return
        
        # Log that background task started
        from backend.utils.agent_deployer import _stream_log
        _stream_log(agent_id, "Background deployment task started")
        
        try:
            await deploy_company_agent(company_id, company_data.name, agent_id=agent_id)
        except Exception as e:
            # Log error but don't fail company creation
            error_msg = str(e)
            _stream_log(agent_id, f"Background task error: {error_msg}")
            
            db.create_audit_log(
                user_id=current_user["user_id"],
                company_id=company_id,
                action="agent_deployment_failed",
                details={"error": error_msg}
            )
            # Ensure company status is set to failed
            db.update_company_agent(company_id, None, "failed")
            
            # Update agent record to failed
            try:
                db.update_agent(agent_id, {
                    "deployment_status": "failed",
                    "deployment_error": error_msg
                })
            except Exception:
                # Agent record might not exist, that's okay
                pass
    
    # Add background task - deployment will run asynchronously
    background_tasks.add_task(deploy_agent_background)
    
    # Log company creation
    db.create_audit_log(
        user_id=current_user["user_id"],
        company_id=company_id,
        action="company_created",
        details={
            "name": company_data.name,
            "admin_email": company_data.admin_email,
            "employee_email": employee_email
        }
    )
    
    # Return response with employee credentials for easy access
    response = CompanyResponse(
        company_id=company["company_id"],
        name=company["name"],
        status=company["status"],
        created_at=datetime.fromisoformat(company["created_at"]),
        vector_db_namespace=company["vector_db_namespace"],
        agent_status=company.get("agent_status"),
        agent_deployment_id=company.get("agent_deployment_id"),
    )
    
    # Add employee credentials to response (for initial setup)
    # Convert to dict to add extra fields
    response_dict = response.dict()
    response_dict["employee_credentials"] = {
        "email": employee_email,
        "password": employee_password,
        "role": "employee"
    }
    response_dict["admin_credentials"] = {
        "email": company_data.admin_email,
        "role": "admin"
    }
    
    return response_dict


@router.get("/companies", response_model=CompanyListResponse)
async def list_companies(
    current_user: dict = Depends(get_current_admin_user)
):
    """List all companies"""
    companies_data = db.list_companies()
    companies = [
        CompanyResponse(
            company_id=c["company_id"],
            name=c["name"],
            status=c["status"],
            created_at=datetime.fromisoformat(c["created_at"]),
            vector_db_namespace=c.get("vector_db_namespace"),
            agent_status=c.get("agent_status"),
            agent_deployment_id=c.get("agent_deployment_id"),
        )
        for c in companies_data
    ]
    return CompanyListResponse(companies=companies, total=len(companies))


@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Get company details"""
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    return CompanyResponse(
        company_id=company["company_id"],
        name=company["name"],
        status=company["status"],
        created_at=datetime.fromisoformat(company["created_at"]),
        vector_db_namespace=company.get("vector_db_namespace"),
        agent_status=company.get("agent_status"),
        agent_deployment_id=company.get("agent_deployment_id"),
    )


@router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    updates: CompanyUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """Update company information"""
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    update_dict = {}
    if updates.name is not None:
        update_dict["name"] = updates.name
    if updates.status is not None:
        update_dict["status"] = updates.status.value
    
    if update_dict:
        updated_company = db.update_company(company_id, update_dict)
        db.create_audit_log(
            user_id=current_user["user_id"],
            company_id=company_id,
            action="company_updated",
            details=update_dict
        )
    else:
        updated_company = company
    
    return CompanyResponse(
        company_id=updated_company["company_id"],
        name=updated_company["name"],
        status=updated_company["status"],
        created_at=datetime.fromisoformat(updated_company["created_at"]),
        vector_db_namespace=updated_company.get("vector_db_namespace"),
        agent_status=updated_company.get("agent_status"),
        agent_deployment_id=updated_company.get("agent_deployment_id"),
    )


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Delete a company and all associated resources"""
    # Verify company exists
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    company_name = company.get("name", company_id)
    vector_db_namespace = company.get("vector_db_namespace")
    
    try:
        # 1. Delete agent if it exists
        agent = db.get_agent_by_company(company_id)
        if agent:
            agent_id = agent["agent_id"]
            
            # Delete agent file if it exists
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            agents_dir = project_root / "agents"
            agent_file = agents_dir / f"company_agent_{company_id}.py"
            
            if agent_file.exists():
                try:
                    agent_file.unlink()
                except Exception as e:
                    print(f"Warning: Failed to delete agent file: {e}")
            
            # Delete agent record
            db.delete_agent(agent_id)
        
        # 2. Delete vector DB namespace
        if vector_db_namespace:
            try:
                vector_db = VectorDBClient()
                vector_db.delete_namespace(vector_db_namespace)
            except Exception as e:
                print(f"Warning: Failed to delete vector DB namespace: {e}")
        
        # 3. Delete all users for the company
        deleted_users_count = db.delete_users_by_company(company_id)
        
        # 4. Delete all audit logs for the company
        deleted_logs_count = db.delete_audit_logs_by_company(company_id)
        
        # 5. Delete the company record itself
        success = db.delete_company(company_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete company record"
            )
        
        # Log deletion action (before deleting audit logs)
        db.create_audit_log(
            user_id=current_user["user_id"],
            company_id="SYSTEM",  # Use SYSTEM since company is being deleted
            action="company_deleted",
            details={
                "deleted_company_id": company_id,
                "deleted_company_name": company_name,
                "deleted_users_count": deleted_users_count,
                "deleted_logs_count": deleted_logs_count
            }
        )
        
        return {
            "message": "Company deleted successfully",
            "deleted_company_id": company_id,
            "deleted_users_count": deleted_users_count,
            "deleted_logs_count": deleted_logs_count
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete company: {str(e)}"
        )


@router.get("/companies/{company_id}/users", response_model=UserListResponse)
async def list_company_users(
    company_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """List all users for a company"""
    users_data = db.get_users_by_company(company_id)
    users = [
        UserResponse(
            user_id=u["user_id"],
            email=u["email"],
            company_id=u["company_id"],
            role=u["role"],
            created_at=datetime.fromisoformat(u["created_at"]),
        )
        for u in users_data
    ]
    return UserListResponse(users=users, total=len(users))


@router.get("/companies/{company_id}/agent", response_model=AgentResponse)
async def get_company_agent(
    company_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Get agent information for a company"""
    # First, try to get agent_id from company record (strongly consistent)
    company = db.get_company(company_id)
    agent = None
    
    if company and company.get("agent_id"):
        # Use agent_id from company record for direct lookup (strongly consistent)
        agent = db.get_agent_by_id(company.get("agent_id"))
    
    # Fallback: try to get agent by company_id scan (eventually consistent)
    if not agent:
        import time
        for attempt in range(5):  # Retry up to 5 times with longer delays
            agent = db.get_agent_by_company(company_id)
            if agent:
                break
            if attempt < 4:  # Don't sleep on last attempt
                time.sleep(0.3)  # Longer delay for eventual consistency
    
    if not agent:
        # Return a pending response instead of 404 to allow frontend to keep polling
        # This handles the case where agent is being created
        return AgentResponse(
            agent_id="pending",
            company_id=company_id,
            deployment_status="pending",
            memory_id=None,
            deployment_id=None,
            agent_arn=None,
            agent_endpoint=None,
            ecr_uri=None,
            codebuild_id=None,
            deployment_error=None,
            deployment_logs=["Agent record is being created..."],
            created_at=datetime.utcnow(),
            updated_at=None,
        )
    
    return AgentResponse(
        agent_id=agent["agent_id"],
        company_id=agent["company_id"],
        deployment_status=agent["deployment_status"],
        memory_id=agent.get("memory_id"),
        deployment_id=agent.get("deployment_id"),
        agent_arn=agent.get("agent_arn"),
        agent_endpoint=agent.get("agent_endpoint"),
        ecr_uri=agent.get("ecr_uri"),
        codebuild_id=agent.get("codebuild_id"),
        deployment_error=agent.get("deployment_error"),
        deployment_logs=agent.get("deployment_logs", []),
        created_at=datetime.fromisoformat(agent["created_at"]),
        updated_at=datetime.fromisoformat(agent["updated_at"]) if agent.get("updated_at") else None,
    )


@router.post("/companies/{company_id}/agent/redeploy")
async def redeploy_company_agent(
    company_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Redeploy an agent for a company"""
    from backend.utils.agent_deployer import redeploy_agent
    
    # Verify company exists
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    try:
        deployment_id = await redeploy_agent(company_id)
        
        # Log redeployment action
        db.create_audit_log(
            user_id=current_user["user_id"],
            company_id=company_id,
            action="agent_redeployed",
            details={"deployment_id": deployment_id}
        )
        
        return {
            "message": "Agent redeployment initiated",
            "deployment_id": deployment_id,
            "status": "deploying"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to redeploy agent: {str(e)}"
        )


@router.delete("/companies/{company_id}/agent")
async def delete_company_agent(
    company_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Delete an agent for a company"""
    # Verify company exists
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # Get agent
    agent = db.get_agent_by_company(company_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found for this company"
        )
    
    agent_id = agent["agent_id"]
    
    # Delete agent file if it exists
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent
    agents_dir = project_root / "agents"
    agent_file = agents_dir / f"company_agent_{company_id}.py"
    
    if agent_file.exists():
        try:
            agent_file.unlink()
        except Exception as e:
            # Log but don't fail if file deletion fails
            print(f"Warning: Failed to delete agent file: {e}")
    
    # Delete agent record from database
    success = db.delete_agent(agent_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent record"
        )
    
    # Update company to remove agent references
    db.update_company(company_id, {
        "agent_deployment_id": None,
        "agent_status": None
    })
    
    # Log deletion action
    db.create_audit_log(
        user_id=current_user["user_id"],
        company_id=company_id,
        action="agent_deleted",
        details={"agent_id": agent_id}
    )
    
    return {
        "message": "Agent deleted successfully",
        "agent_id": agent_id
    }


@router.get("/companies/{company_id}/audit-logs", response_model=AuditLogListResponse)
async def get_company_audit_logs(
    company_id: str,
    limit: int = 100,
    current_user: dict = Depends(get_current_admin_user)
):
    """Get audit logs for a company"""
    logs_data = db.get_audit_logs_by_company(company_id, limit=limit)
    logs = [
        AuditLogEntry(
            log_id=l["log_id"],
            timestamp=datetime.fromisoformat(l["timestamp"]),
            user_id=l["user_id"],
            company_id=l["company_id"],
            action=l["action"],
            details=l["details"],
        )
        for l in logs_data
    ]
    return AuditLogListResponse(logs=logs, total=len(logs))


@router.post("/companies/{company_id}/knowledge-base/upload")
async def upload_knowledge_base(
    company_id: str,
    data: KnowledgeBaseUpload,
    current_user: dict = Depends(get_current_admin_user)
):
    """Upload knowledge base data for a company"""
    try:
        company = db.get_company(company_id)
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
        
        namespace = company.get("vector_db_namespace")
        if not namespace:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vector database namespace not configured for company"
            )
        
        # Validate input data
        if not data.data or len(data.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data provided. Please provide at least one FAQ entry."
            )
        
        # Initialize vector database client
        try:
            vector_db = VectorDBClient()
            if vector_db.index is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Vector database not available. Please check Pinecone configuration."
                )
        except ImportError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vector database client error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize vector database: {str(e)}"
            )
        
        # Generate embeddings
        # IMPORTANT: The embeddings model dimension must match the Pinecone index dimension
        # Supports both HuggingFace (free) and OpenAI (requires API key) embeddings
        import os
        embeddings_provider = os.getenv("EMBEDDINGS_PROVIDER", "huggingface").lower()
        embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "")
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        
        try:
            if embeddings_provider == "openai" or openai_api_key:
                # Use OpenAI embeddings (1536 dimensions)
                if not OPENAI_AVAILABLE:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="OpenAI embeddings not available. Install with: pip install langchain-openai"
                    )
                if not openai_api_key:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="OPENAI_API_KEY environment variable is required for OpenAI embeddings"
                    )
                
                # Use specified model or default to text-embedding-ada-002 (1536 dims)
                # Note: text-embedding-3-large produces 3072 dimensions
                #       text-embedding-ada-002 and text-embedding-3-small produce 1536 dimensions
                model_name = embeddings_model_name or "text-embedding-ada-002"
                embeddings_model = OpenAIEmbeddings(
                    model=model_name,
                    openai_api_key=openai_api_key
                )
                
                # Warn if using text-embedding-3-large (3072 dims) - requires matching Pinecone index
                if model_name == "text-embedding-3-large":
                    import logging
                    logging.warning("Using text-embedding-3-large (3072 dimensions). Ensure Pinecone index is configured for 3072 dimensions.")
            else:
                # Use HuggingFace embeddings (default: 384 dimensions)
                model_name = embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
                embeddings_model = HuggingFaceEmbeddings(
                    model_name=model_name
                )
            
            # Test embedding to get dimension
            test_embedding = embeddings_model.embed_query("test")
            embedding_dim = len(test_embedding)
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize embeddings model: {str(e)}"
            )
        
        # Prepare documents
        documents = []
        for entry in data.data:
            question = entry.get("question", "")
            answer = entry.get("answer", "")
            if not question or not answer:
                continue  # Skip empty entries
            text = f"Q: {question}\nA: {answer}"
            documents.append({
                "text": text,
                "question": question,
                "answer": answer
            })
        
        if len(documents) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid FAQ entries found. Please provide entries with both question and answer."
            )
        
        # Generate embeddings
        try:
            texts = [doc["text"] for doc in documents]
            embeddings = embeddings_model.embed_documents(texts)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate embeddings: {str(e)}"
            )
        
        # Upload to vector database
        try:
            success = vector_db.upsert_documents(namespace, documents, embeddings)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to upload knowledge base to vector database"
                )
        except Exception as e:
            error_msg = str(e)
            # Check if it's a dimension mismatch error
            if "dimension" in error_msg.lower() and "does not match" in error_msg.lower():
                # Extract the dimensions from error message
                import re
                dim_match = re.search(r'dimension (\d+) does not match.*dimension (\d+)', error_msg)
                if dim_match:
                    embedding_dim = dim_match.group(1)
                    index_dim = dim_match.group(2)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Embedding dimension mismatch: Model produces {embedding_dim}-dimensional vectors, but Pinecone index requires {index_dim}-dimensional vectors. Please set EMBEDDINGS_MODEL_NAME environment variable to a model that produces {index_dim} dimensions, or recreate the Pinecone index with dimension {embedding_dim}."
                    )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload knowledge base: {error_msg}"
            )
        
        # Log upload
        try:
            db.create_audit_log(
                user_id=current_user["user_id"],
                company_id=company_id,
                action="knowledge_base_uploaded",
                details={"entries_count": len(documents)}
            )
        except Exception:
            pass  # Don't fail if audit log fails
        
        return {
            "message": "Knowledge base uploaded successfully",
            "entries_count": len(documents),
            "namespace": namespace
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Unexpected error in upload_knowledge_base: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/companies/{company_id}/vector-db/stats")
async def get_vector_db_stats(
    company_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Get vector database statistics for a company"""
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    namespace = company.get("vector_db_namespace")
    if not namespace:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vector database namespace not configured for company"
        )
    
    vector_db = VectorDBClient()
    stats = vector_db.get_namespace_stats(namespace)
    
    return {
        "namespace": namespace,
        "total_entries": stats.get("total_entries", 0),
        "last_updated": stats.get("last_updated"),
        "index_name": getattr(vector_db, 'index_name', None)
    }


@router.get("/companies/{company_id}/knowledge-base/stats", response_model=KnowledgeBaseStats)
async def get_knowledge_base_stats(
    company_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Get knowledge base statistics for a company"""
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    vector_db = VectorDBClient()
    namespace = company.get("vector_db_namespace")
    if not namespace:
        return KnowledgeBaseStats(
            company_id=company_id,
            total_entries=0,
            last_updated=None
        )
    
    stats = vector_db.get_namespace_stats(namespace)
    return KnowledgeBaseStats(
        company_id=company_id,
        total_entries=stats.get("total_entries", 0),
        last_updated=datetime.fromisoformat(stats["last_updated"]) if stats.get("last_updated") else None
    )


@router.get("/companies/{company_id}/knowledge-base/entries", response_model=KnowledgeBaseListResponse)
async def list_knowledge_base_entries(
    company_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """List all knowledge base entries for a company"""
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    vector_db = VectorDBClient()
    namespace = company.get("vector_db_namespace")
    if not namespace:
        return KnowledgeBaseListResponse(entries=[], total=0)
    
    try:
        vectors = vector_db.list_vectors(namespace, limit=10000)
        entries = [
            KnowledgeBaseEntry(
                id=v.get("id", ""),
                question=v.get("question", ""),
                answer=v.get("answer", ""),
                text=v.get("text", "")
            )
            for v in vectors
        ]
        return KnowledgeBaseListResponse(entries=entries, total=len(entries))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list knowledge base entries: {str(e)}"
        )


@router.delete("/companies/{company_id}/knowledge-base/entries")
async def delete_knowledge_base_entries(
    company_id: str,
    delete_request: KnowledgeBaseDeleteRequest,
    current_user: dict = Depends(get_current_admin_user)
):
    """Delete knowledge base entries (all or selected)"""
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    vector_db = VectorDBClient()
    namespace = company.get("vector_db_namespace")
    if not namespace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No knowledge base namespace found for this company"
        )
    
    try:
        if delete_request.vector_ids is None or len(delete_request.vector_ids) == 0:
            # Delete all entries
            success = vector_db.delete_namespace(namespace)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete all knowledge base entries"
                )
            
            # Log action
            db.create_audit_log(
                user_id=current_user["user_id"],
                company_id=company_id,
                action="knowledge_base_deleted_all",
                details={"namespace": namespace}
            )
            
            return {"message": "All knowledge base entries deleted successfully", "deleted_count": "all"}
        else:
            # Delete selected entries
            success = vector_db.delete_vectors(namespace, delete_request.vector_ids)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete selected knowledge base entries"
                )
            
            # Log action
            db.create_audit_log(
                user_id=current_user["user_id"],
                company_id=company_id,
                action="knowledge_base_deleted_selected",
                details={"namespace": namespace, "vector_ids": delete_request.vector_ids, "count": len(delete_request.vector_ids)}
            )
            
            return {"message": f"{len(delete_request.vector_ids)} knowledge base entries deleted successfully", "deleted_count": len(delete_request.vector_ids)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete knowledge base entries: {str(e)}"
        )
