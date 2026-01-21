"""Company employee routes for chat and agent interaction"""
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime
import boto3
import os
import json
import uuid

from backend.models import ChatMessage, ChatResponse
from backend.auth import get_current_company_user, verify_company_access
from backend.database import db

router = APIRouter(prefix="/company", tags=["company"])


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    message: ChatMessage,
    current_user: dict = Depends(get_current_company_user)
):
    """Send a message to the company's agent and get a response"""
    company_id = current_user["company_id"]
    user_id = current_user["user_id"]
    
    # Get company and agent info
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # Try to get agent - first by agent_id from company record (strongly consistent), then by company_id scan
    agent = None
    
    # Method 1: Use agent_id from company record if available (strongly consistent)
    if company.get("agent_id"):
        agent = db.get_agent_by_id(company.get("agent_id"))
    
    # Method 2: Fallback to scan by company_id (eventually consistent)
    if not agent:
        import time
        for attempt in range(5):  # Retry up to 5 times
            agent = db.get_agent_by_company(company_id)
            if agent:
                break
            if attempt < 4:  # Don't sleep on last attempt
                time.sleep(0.2)  # Small delay for eventual consistency
    
    if not agent:
        # Provide more helpful error message
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not deployed for this company. Company ID: {company_id}. Please contact administrator to deploy the agent."
        )
    
    # Check agent status
    deployment_status = agent.get("deployment_status", "unknown")
    if deployment_status != "active":
        status_message = {
            "pending": "Agent deployment is in progress. Please wait a few minutes and try again.",
            "deploying": "Agent deployment is in progress. Please wait a few minutes and try again.",
            "failed": "Agent deployment failed. Please contact administrator.",
            "unknown": "Agent status is unknown. Please contact administrator."
        }.get(deployment_status, f"Agent status is '{deployment_status}'. Please contact administrator.")
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=status_message
        )
    
    # Check for agent ARN (required for invocation)
    agent_arn = agent.get("agent_arn")
    if not agent_arn:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent runtime ARN not found. The agent may not be fully deployed yet. Please contact administrator."
        )
    
    # Use session_id from message or generate one
    session_id = message.session_id or f"{user_id}_{company_id}"
    
    # Invoke agent via AWS Bedrock AgentCore Runtime
    try:
        bedrock_agentcore = boto3.client(
            'bedrock-agentcore',
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        # runtimeSessionId must be 33+ chars; extend if needed
        runtime_session_id = session_id
        if len(runtime_session_id) < 33:
            runtime_session_id = f"{runtime_session_id}-{uuid.uuid4().hex}"[:33]
        
        payload = json.dumps({
            "prompt": message.message,
            "company_id": company_id,
            "actor_id": user_id,
            "thread_id": runtime_session_id
        })
        
        response = bedrock_agentcore.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=runtime_session_id,
            payload=payload,
            qualifier="DEFAULT"
        )
        
        # Parse response
        response_text = ""
        try:
            response_body = response['response'].read()
            response_data = json.loads(response_body)
            if 'output' in response_data:
                output = response_data['output']
                if 'message' in output:
                    message_obj = output['message']
                    if 'content' in message_obj:
                        for content_item in message_obj['content']:
                            if 'text' in content_item:
                                response_text += content_item['text']
            if not response_text:
                response_text = response_data.get('result', 'No response generated')
        except Exception:
            response_text = "No response generated"
        
    except Exception as e:
        # Log error
        db.create_audit_log(
            user_id=user_id,
            company_id=company_id,
            action="agent_invocation_failed",
            details={"error": str(e), "message": message.message}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invoke agent: {str(e)}"
        )
    
    # Log successful invocation
    db.create_audit_log(
        user_id=user_id,
        company_id=company_id,
        action="agent_invocation",
        details={
            "session_id": session_id,
            "query": message.message,
            "response_length": len(response_text)
        }
    )
    
    return ChatResponse(
        response=response_text,
        session_id=session_id,
        timestamp=datetime.utcnow()
    )


@router.get("/info")
async def get_company_info(
    current_user: dict = Depends(get_current_company_user)
):
    """Get current user's company information"""
    company_id = current_user["company_id"]
    company = db.get_company(company_id)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    return {
        "company_id": company["company_id"],
        "name": company["name"],
        "status": company["status"],
    }
