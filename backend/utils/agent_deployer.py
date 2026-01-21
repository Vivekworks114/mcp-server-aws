"""
Production-grade agent deployment using Docker + ECR + Bedrock AgentCore Control API
Stateless agents (NO memory, NO conversation persistence)
"""
import os
import subprocess
import uuid
import boto3
import re
import time
import asyncio
import shutil
import base64
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List
from pathlib import Path
from datetime import datetime

from backend.database import db
from agents.agent_factory import create_company_agent_file_stateless

# Thread pool executor for blocking I/O operations
_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="agent_deploy")


# ------------------------------------------------------------
# Utility: ANSI code cleanup
# ------------------------------------------------------------

def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


# ------------------------------------------------------------
# Utility: Real-time log streaming
# ------------------------------------------------------------

def _stream_log(agent_id: str, line: str) -> None:
    """
    Stream a single log line in real-time:
    - Clean ANSI codes
    - Add timestamp
    - Persist immediately to database
    """
    if not line or not line.strip():
        return
    
    # Clean ANSI codes
    clean_line = _strip_ansi(line.strip())
    if not clean_line:
        return
    
    # Add timestamp
    timestamp = datetime.utcnow().isoformat()
    log_entry = f"[{timestamp}] {clean_line}"
    
    # Get current logs and append
    agent = db.get_agent_by_id(agent_id)
    logs = agent.get("deployment_logs", []) if agent else []
    logs.append(log_entry)
    
    # Keep only last 100 entries
    logs = logs[-100:]
    
    # Persist immediately
    db.update_agent(agent_id, {"deployment_logs": logs})


# ------------------------------------------------------------
# ECR Repository Management
# ------------------------------------------------------------

def _ensure_ecr_repository(ecr_client, repository_name: str, region: str, agent_id: str) -> str:
    """Ensure ECR repository exists, create if not"""
    try:
        response = ecr_client.describe_repositories(repositoryNames=[repository_name])
        repository_uri = response['repositories'][0]['repositoryUri']
        _stream_log(agent_id, f"ECR repository exists: {repository_uri}")
        return repository_uri
    except ecr_client.exceptions.RepositoryNotFoundException:
        _stream_log(agent_id, f"Creating ECR repository: {repository_name}")
        response = ecr_client.create_repository(repositoryName=repository_name)
        repository_uri = response['repository']['repositoryUri']
        _stream_log(agent_id, f"ECR repository created: {repository_uri}")
        return repository_uri


def _get_ecr_login_token(ecr_client, region: str, agent_id: str = "") -> str:
    """Get ECR login password for Docker authentication"""
    response = ecr_client.get_authorization_token()
    token = response['authorizationData'][0]['authorizationToken']
    # Token is base64 encoded "AWS:password", decode and extract password
    try:
        decoded = base64.b64decode(token).decode('utf-8')
        password = decoded.split(':')[1]  # Extract password part
        return password
    except Exception as e:
        # Fallback: try using AWS CLI command
        if agent_id:
            _stream_log(agent_id, f"Warning: Could not decode token, trying AWS CLI: {str(e)}")
        try:
            result = subprocess.run(
                ["aws", "ecr", "get-login-password", "--region", region],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception as cli_error:
            raise Exception(f"Failed to get ECR login password: {str(e)} (CLI fallback also failed: {str(cli_error)})")


# ------------------------------------------------------------
# Docker Build and Push
# ------------------------------------------------------------

def _build_docker_image(
    agent_id: str,
    dockerfile_path: Path,
    build_context: Path,
    image_tag: str,
    company_id: str,
    company_name: str,
    vector_db_namespace: str
) -> None:
    """Build Docker image for company agent"""
    _stream_log(agent_id, f"Building Docker image: {image_tag}")
    
    # Build command
    build_cmd = [
        "docker", "build",
        "-f", str(dockerfile_path),
        "-t", image_tag,
        "--build-arg", f"COMPANY_ID={company_id}",
        "--build-arg", f"COMPANY_NAME={company_name}",
        "--build-arg", f"VECTOR_DB_NAMESPACE={vector_db_namespace}",
        str(build_context)
    ]
    
    _stream_log(agent_id, f"Running: {' '.join(build_cmd)}")
    
    process = subprocess.Popen(
        build_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(build_context)
    )
    
    # Stream build output
    for line in process.stdout:
        if line:
            _stream_log(agent_id, line.rstrip())
    
    return_code = process.wait()
    if return_code != 0:
        raise Exception(f"Docker build failed with return code {return_code}")
    
    _stream_log(agent_id, f"Docker image built successfully: {image_tag}")


def _push_docker_image(agent_id: str, image_tag: str, ecr_uri: str, region: str) -> None:
    """Push Docker image to ECR"""
    _stream_log(agent_id, f"Pushing Docker image to ECR: {ecr_uri}")
    
    # Get ECR login password
    ecr_client = boto3.client('ecr', region_name=region)
    password = _get_ecr_login_token(ecr_client, region, agent_id)
    
    # Extract registry URL from ECR URI
    registry = ecr_uri.split('/')[0]
    
    # Login to ECR using subprocess with stdin
    _stream_log(agent_id, "Authenticating with ECR...")
    
    login_process = subprocess.Popen(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    stdout, stderr = login_process.communicate(input=password)
    
    if login_process.returncode != 0:
        error_msg = stderr if stderr else stdout
        raise Exception(f"ECR login failed: {error_msg}")
    
    _stream_log(agent_id, "ECR authentication successful")
    
    # Tag image with ECR URI
    _stream_log(agent_id, f"Tagging image: {image_tag} -> {ecr_uri}")
    tag_process = subprocess.run(
        ["docker", "tag", image_tag, ecr_uri],
        capture_output=True,
        text=True
    )
    
    if tag_process.returncode != 0:
        raise Exception(f"Failed to tag image: {tag_process.stderr}")
    
    # Push image
    _stream_log(agent_id, f"Pushing image to ECR: {ecr_uri}")
    push_process = subprocess.Popen(
        ["docker", "push", ecr_uri],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Stream push output
    for line in push_process.stdout:
        if line:
            _stream_log(agent_id, line.rstrip())
    
    return_code = push_process.wait()
    if return_code != 0:
        raise Exception(f"Docker push failed with return code {return_code}")
    
    _stream_log(agent_id, f"Image pushed successfully: {ecr_uri}")


# ------------------------------------------------------------
# Main deployment function (synchronous)
# ------------------------------------------------------------

def _deploy_company_agent_sync(company_id: str, company_name: str, agent_id: Optional[str] = None) -> str:
    """
    Synchronous deployment function - runs blocking operations
    This is called from a thread pool executor to avoid blocking the event loop
    
    Args:
        company_id: Company ID
        company_name: Company name
        agent_id: Optional agent ID (if agent record already exists)
    """
    
    # --------------------------------------------------------
    # Initial DB setup
    # --------------------------------------------------------
    
    company = db.get_company(company_id)
    if not company:
        raise Exception("Company not found")
    
    vector_db_namespace = company.get("vector_db_namespace", f"company_{company_id}")
    
    # Check if agent record already exists (created in route handler)
    if agent_id:
        existing_agent = db.get_agent_by_id(agent_id)
        if not existing_agent:
            raise Exception(f"Agent ID provided but not found: {agent_id}")
    else:
        # No agent ID provided, create new
        agent_id = str(uuid.uuid4())
        db.create_agent(
            agent_id=agent_id,
            company_id=company_id,
            memory_id=None  # Stateless - no memory
        )
    
    _stream_log(agent_id, "Deployment started (stateless agent)")
    db.update_agent(agent_id, {
        "deployment_status": "deploying",
        "deployment_logs": []
    })
    db.update_company_agent(company_id, None, "deploying")
    
    try:
        # ----------------------------------------------------
        # AWS Configuration
        # ----------------------------------------------------
        
        region = os.getenv("AWS_REGION", "us-east-1")
        aws_account_id = boto3.client('sts', region_name=region).get_caller_identity()['Account']
        
        # Get IAM role ARN
        iam_role_arn = os.getenv("AGENTCORE_IAM_ROLE_ARN")
        if not iam_role_arn:
            raise Exception("AGENTCORE_IAM_ROLE_ARN environment variable not set")
        
        # Ensure IAM role ARN is complete
        if not iam_role_arn.startswith("arn:aws:iam::"):
            iam_role_arn = f"arn:aws:iam::{aws_account_id}:role/{iam_role_arn}"
        
        _stream_log(agent_id, f"Using IAM role: {iam_role_arn}")
        
        # ----------------------------------------------------
        # Secrets
        # ----------------------------------------------------
        
        secrets_client = boto3.client("secretsmanager", region_name=region)
        
        try:
            groq_key = secrets_client.get_secret_value(
                SecretId="agentcore/groq-api-key"
            )["SecretString"]
        except Exception as e:
            raise Exception(f"Failed to retrieve Groq API key from Secrets Manager: {str(e)}")
        
        try:
            hf_token = secrets_client.get_secret_value(
                SecretId="agentcore/huggingface-token"
            )["SecretString"]
        except Exception:
            hf_token = ""
        
        try:
            pinecone_key = secrets_client.get_secret_value(
                SecretId="agentcore/pinecone-api-key"
            )["SecretString"]
        except Exception:
            pinecone_key = os.getenv("PINECONE_API_KEY", "")
        
        # Store embeddings model name in Secrets Manager to ensure agent uses same as backend
        embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "")
        if embeddings_model_name:
            try:
                # Try to update existing secret
                secrets_client.update_secret(
                    SecretId="agentcore/embeddings-model-name",
                    SecretString=embeddings_model_name
                )
                _stream_log(agent_id, f"Updated embeddings model name in Secrets Manager: {embeddings_model_name}")
            except Exception:
                # If secret doesn't exist, create it
                try:
                    secrets_client.create_secret(
                        Name="agentcore/embeddings-model-name",
                        SecretString=embeddings_model_name,
                        Description="Embeddings model name for agent runtime (must match backend)"
                    )
                    _stream_log(agent_id, f"Created embeddings model name in Secrets Manager: {embeddings_model_name}")
                except Exception as e:
                    # Secret might already exist or other error - log but don't fail
                    _stream_log(agent_id, f"Note: Could not store embeddings model name in Secrets Manager: {str(e)}")
        
        _stream_log(agent_id, "Secrets retrieved from AWS Secrets Manager")
        
        # ----------------------------------------------------
        # Generate stateless agent file
        # ----------------------------------------------------
        
        project_root = Path(__file__).parent.parent.parent
        agents_dir = project_root / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        agent_file_path = create_company_agent_file_stateless(
            company_id=company_id,
            company_name=company_name,
            vector_db_namespace=vector_db_namespace,
            output_dir=agents_dir
        )
        
        if not agent_file_path.exists():
            raise Exception(f"Agent file not created: {agent_file_path}")
        
        _stream_log(agent_id, f"Stateless agent file created: {agent_file_path}")
        
        # Copy requirements.txt to agents directory for Docker build
        requirements_src = project_root / "requirements.txt"
        requirements_dst = agents_dir / "requirements.txt"
        if requirements_src.exists():
            shutil.copy2(requirements_src, requirements_dst)
            _stream_log(agent_id, f"Copied requirements.txt to Docker build context: {requirements_dst}")
        else:
            raise Exception(f"requirements.txt not found at: {requirements_src}")
        
        # Copy generated file to a fixed build name that won't overwrite the template
        # The template file (company_agent_stateless.py) must remain untouched
        # Using a fixed name since only one build happens at a time
        build_agent_filename = "company_agent_stateless_build.py"
        build_agent_file = agents_dir / build_agent_filename
        
        # Remove any existing build file first (from previous failed builds)
        if build_agent_file.exists():
            build_agent_file.unlink()
        
        shutil.copy2(agent_file_path, build_agent_file)
        _stream_log(agent_id, f"Copied generated agent file to build context: {build_agent_file}")
        
        # ----------------------------------------------------
        # ECR Repository Setup
        # ----------------------------------------------------
        
        ecr_repo_name = os.getenv("ECR_REPOSITORY_NAME", "agentcore-agents")
        ecr_client = boto3.client('ecr', region_name=region)
        ecr_uri = _ensure_ecr_repository(ecr_client, ecr_repo_name, region, agent_id)
        
        # Image tag (use company_id for uniqueness)
        image_tag = f"{ecr_uri}:{company_id}"
        _stream_log(agent_id, f"ECR repository URI: {ecr_uri}")
        _stream_log(agent_id, f"Image tag: {image_tag}")
        
        # ----------------------------------------------------
        # Build Docker Image
        # ----------------------------------------------------
        
        dockerfile_path = agents_dir / "Dockerfile"
        if not dockerfile_path.exists():
            raise Exception(f"Dockerfile not found: {dockerfile_path}")
        
        _build_docker_image(
            agent_id=agent_id,
            dockerfile_path=dockerfile_path,
            build_context=agents_dir,
            image_tag=image_tag,
            company_id=company_id,
            company_name=company_name,
            vector_db_namespace=vector_db_namespace
        )
        
        # Clean up build-specific file after successful build
        try:
            if build_agent_file.exists():
                build_agent_file.unlink()
                _stream_log(agent_id, f"Cleaned up build file: {build_agent_file}")
        except Exception as e:
            _stream_log(agent_id, f"Note: Could not clean up build file: {str(e)}")
        
        # ----------------------------------------------------
        # Push Docker Image to ECR
        # ----------------------------------------------------
        
        _push_docker_image(
            agent_id=agent_id,
            image_tag=image_tag,
            ecr_uri=image_tag,  # Same as image_tag since we tagged it
            region=region
        )
        
        # ----------------------------------------------------
        # Create Agent Runtime using Bedrock AgentCore Control API
        # ----------------------------------------------------
        
        _stream_log(agent_id, "Creating agent runtime using Bedrock AgentCore Control API")
        
        # Generate safe agent runtime name
        # AWS pattern: [a-zA-Z][a-zA-Z0-9_]{0,47} - must start with letter, only letters/numbers/underscores
        clean_name = re.sub(r"[^a-zA-Z0-9]", "_", company_name)[:30]
        if not clean_name or not clean_name[0].isalpha():
            clean_name = "Company"
        
        # Remove hyphens from company_id and use underscore separator
        company_id_clean = company_id.replace('-', '')[:8]
        agent_runtime_name = f"{clean_name}_{company_id_clean}".lower()[:48]
        
        # Ensure it starts with a letter (required by AWS)
        if not agent_runtime_name[0].isalpha():
            agent_runtime_name = f"agent_{agent_runtime_name}"[:48]
        
        bedrock_client = boto3.client('bedrock-agentcore-control', region_name=region)
        
        try:
            response = bedrock_client.create_agent_runtime(
                agentRuntimeName=agent_runtime_name,
                agentRuntimeArtifact={
                    'containerConfiguration': {
                        'containerUri': image_tag
                    }
                },
                networkConfiguration={"networkMode": "PUBLIC"},
                roleArn=iam_role_arn
            )
            
            agent_runtime_arn = response['agentRuntimeArn']
            status = response.get('status', 'CREATING')
            
            _stream_log(agent_id, f"Agent runtime created successfully!")
            _stream_log(agent_id, f"Agent Runtime ARN: {agent_runtime_arn}")
            _stream_log(agent_id, f"Status: {status}")
            
            # Extract deployment ID from ARN
            # Format: arn:aws:bedrock-agentcore:region:account:agent-runtime/runtime-name
            deployment_id = agent_runtime_arn.split('/')[-1] if '/' in agent_runtime_arn else agent_runtime_name
            
            # Wait for runtime to be ready (poll status)
            # Note: Agent runtime creation is asynchronous, status polling is optional
            _stream_log(agent_id, "Agent runtime creation initiated. Status polling skipped (runtime will become active asynchronously).")
            endpoint_url = ''
            
            # Try to get runtime details if the method exists
            # Some boto3 versions may have different method names
            try:
                # Try get_agent_runtime (common boto3 pattern)
                try:
                    get_response = bedrock_client.get_agent_runtime(
                        agentRuntimeName=agent_runtime_name
                    )
                    current_status = get_response.get('status', status)
                    endpoint_url = get_response.get('endpointUrl', '')
                    _stream_log(agent_id, f"Agent runtime status: {current_status}")
                    if endpoint_url:
                        _stream_log(agent_id, f"Agent endpoint URL: {endpoint_url}")
                except AttributeError:
                    # Method doesn't exist, try list_agent_runtimes and filter
                    try:
                        list_response = bedrock_client.list_agent_runtimes()
                        # Find our runtime in the list
                        for runtime in list_response.get('agentRuntimes', []):
                            if runtime.get('agentRuntimeName') == agent_runtime_name:
                                current_status = runtime.get('status', status)
                                endpoint_url = runtime.get('endpointUrl', '')
                                _stream_log(agent_id, f"Agent runtime status: {current_status}")
                                if endpoint_url:
                                    _stream_log(agent_id, f"Agent endpoint URL: {endpoint_url}")
                                break
                    except Exception as list_error:
                        _stream_log(agent_id, f"Could not poll runtime status: {str(list_error)}")
                        _stream_log(agent_id, "Runtime was created successfully. Check AWS Console for status.")
            except Exception as e:
                _stream_log(agent_id, f"Could not retrieve runtime details: {str(e)}")
                _stream_log(agent_id, "Runtime was created successfully. Check AWS Console for status.")
                endpoint_url = ''
            
        except Exception as e:
            error_msg = str(e)
            _stream_log(agent_id, f"ERROR creating agent runtime: {error_msg}")
            raise Exception(f"Failed to create agent runtime: {error_msg}")
        
        # ----------------------------------------------------
        # Update database with deployment info
        # ----------------------------------------------------
        
        agent = db.get_agent_by_id(agent_id)
        logs = agent.get("deployment_logs", []) if agent else []
        
        db.update_agent(
            agent_id,
            {
                "deployment_id": deployment_id,
                "deployment_status": "active",
                "deployment_logs": logs,
                "agent_arn": agent_runtime_arn,
                "agent_endpoint": endpoint_url,
                "ecr_uri": image_tag,
                "codebuild_id": None,  # Not used in container deployment
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        
        db.update_company_agent(company_id, deployment_id, "active")
        _stream_log(agent_id, f"Deployment completed successfully: {deployment_id}")
        
        return deployment_id
        
    except Exception as e:
        _stream_log(agent_id, f"ERROR: {str(e)}")
        agent = db.get_agent_by_id(agent_id)
        logs = agent.get("deployment_logs", []) if agent else []
        
        db.update_agent(
            agent_id,
            {
                "deployment_status": "failed",
                "deployment_error": str(e),
                "deployment_logs": logs,
            },
        )
        db.update_company_agent(company_id, None, "failed")
        raise


# ------------------------------------------------------------
# Async wrapper (runs sync function in thread pool)
# ------------------------------------------------------------

async def deploy_company_agent(company_id: str, company_name: str, agent_id: Optional[str] = None) -> str:
    """
    Async wrapper that runs the blocking deployment in a thread pool executor
    This prevents blocking the FastAPI event loop
    
    Args:
        company_id: Company ID
        company_name: Company name
        agent_id: Optional agent ID (if agent record already exists)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _deploy_company_agent_sync,
        company_id,
        company_name,
        agent_id
    )


# ------------------------------------------------------------
# Redeploy
# ------------------------------------------------------------

async def redeploy_agent(company_id: str) -> str:
    agent = db.get_agent_by_company(company_id)
    company = db.get_company(company_id)
    
    if not agent or not company:
        raise Exception("Agent or company not found")
    
    _stream_log(agent["agent_id"], "Redeployment started")
    db.update_agent(agent["agent_id"], {
        "deployment_status": "deploying",
        "deployment_logs": []
    })
    
    db.update_company_agent(company_id, None, "deploying")
    
    return await deploy_company_agent(company_id, company["name"], agent["agent_id"])


# ------------------------------------------------------------
# Status
# ------------------------------------------------------------

def get_agent_status(company_id: str) -> Optional[dict]:
    return db.get_agent_by_company(company_id)
