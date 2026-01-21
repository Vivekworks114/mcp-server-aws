"""Stateless company-specific agent template (NO memory, NO conversation persistence)"""
import os
from typing import List
import boto3
from botocore.exceptions import ClientError
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langchain_huggingface import HuggingFaceEmbeddings
try:
    from langchain_openai import OpenAIEmbeddings
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Company-specific configuration (injected at build time via agent_factory)
# These placeholders are replaced dynamically per company during deployment
COMPANY_ID = "PLACEHOLDER_COMPANY_ID"
COMPANY_NAME = "PLACEHOLDER_COMPANY_NAME"
VECTOR_DB_NAMESPACE = "PLACEHOLDER_VECTOR_DB_NAMESPACE"

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def _get_secret(secret_name: str, default: str = "") -> str:
    """Fetch secret from AWS Secrets Manager; fall back to default if missing."""
    try:
        client = boto3.client("secretsmanager", region_name=AWS_REGION)
        resp = client.get_secret_value(SecretId=secret_name)
        return resp.get("SecretString") or default
    except ClientError:
        return default
    except Exception:
        return default


GROQ_API_KEY = os.getenv("GROQ_API_KEY") or _get_secret("agentcore/groq-api-key", "")
HF_API_KEY = os.getenv("HF_API_KEY", "") or _get_secret("agentcore/huggingface-token", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "") or _get_secret("agentcore/pinecone-api-key", "")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", "mcp-server")

# Initialize AgentCore app (stateless - no memory components)
app = BedrockAgentCoreApp()

# Initialize embeddings
# IMPORTANT: Must match the dimension of your Pinecone index and backend configuration
# Supports both HuggingFace (free) and OpenAI (requires API key) embeddings
# HuggingFace default: 384 dimensions (all-MiniLM-L6-v2)
# OpenAI default: 1536 dimensions (text-embedding-ada-002)
# OpenAI large: 3072 dimensions (text-embedding-3-large)
import os
embeddings_provider = os.getenv("EMBEDDINGS_PROVIDER", "huggingface").lower()
# Read embeddings model name from environment variable or Secrets Manager
# This ensures agent uses same model as backend
embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "") or _get_secret("agentcore/embeddings-model-name", "")
openai_api_key = os.getenv("OPENAI_API_KEY", "") or _get_secret("agentcore/openai-api-key", "")

if embeddings_provider == "openai" or openai_api_key:
    # Use OpenAI embeddings
    if OPENAI_AVAILABLE and openai_api_key:
        # Default to text-embedding-ada-002 (1536 dims) if not specified
        # Backend should set agentcore/embeddings-model-name secret to match its configuration
        model_name = embeddings_model_name or "text-embedding-ada-002"
        emb = OpenAIEmbeddings(
            model=model_name,
            openai_api_key=openai_api_key
        )
    else:
        # Fallback to HuggingFace if OpenAI not available
        model_name = embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
        emb = HuggingFaceEmbeddings(model_name=model_name)
else:
    # Use HuggingFace embeddings (default: 384 dimensions)
    model_name = embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
    emb = HuggingFaceEmbeddings(model_name=model_name)

# Initialize vector database client
try:
    from pinecone import Pinecone
    
    if PINECONE_API_KEY:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        try:
            vector_index = pc.Index(PINECONE_INDEX)
        except Exception:
            vector_index = None
    else:
        vector_index = None
except ImportError:
    vector_index = None


@tool
def search_faq(query: str) -> str:
    """Search the FAQ knowledge base for relevant information.
    Use this tool when the user asks questions about products, services, or policies.
    
    IMPORTANT: This tool only searches data for {COMPANY_NAME}. Never access data from other companies.
    
    Args:
        query: The search query to find relevant FAQ entries
        
    Returns:
        Relevant FAQ entries that might answer the question
    """
    if vector_index is None:
        return "Vector database not configured. Please contact administrator."
    
    # Generate query embedding
    try:
        query_embedding = emb.embed_query(query)
    except Exception as e:
        return f"Error generating embedding: {str(e)}"
    
    # Search only in company's namespace
    try:
        results = vector_index.query(
            vector=query_embedding,
            top_k=5,  # Increased from 3 to 5 for better coverage
            namespace=VECTOR_DB_NAMESPACE,  # CRITICAL: Company isolation
            include_metadata=True
        )
        
        matches = results.get("matches", [])
        if not matches:
            return f"No relevant FAQ entries found in {COMPANY_NAME}'s knowledge base for query: '{query}'"
        
        # Include similarity scores in response to help LLM understand relevance
        context_parts = []
        for i, match in enumerate(matches, 1):
            score = match.get('score', 0.0)
            metadata = match.get('metadata', {})
            question = metadata.get('question', '')
            answer = metadata.get('answer', '')
            context_parts.append(
                f"FAQ Entry {i} (relevance: {score:.3f}):\nQ: {question}\nA: {answer}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        return f"Found {len(matches)} relevant FAQ entries from {COMPANY_NAME}:\n\n{context}\n\nUse this information to answer the user's question, even if the relevance scores seem low."
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"Error searching knowledge base: {str(e)}\n\nDetails: {error_details}"


@tool
def search_detailed_faq(query: str, num_results: int = 5) -> str:
    """Search the FAQ knowledge base with more results for complex queries.
    Use this when the initial search doesn't provide enough information.
    
    IMPORTANT: This tool only searches data for {COMPANY_NAME}. Never access data from other companies.
    
    Args:
        query: The search query
        num_results: Number of results to retrieve (default: 5)
        
    Returns:
        More comprehensive FAQ entries
    """
    if vector_index is None:
        return "Vector database not configured. Please contact administrator."
    
    query_embedding = emb.embed_query(query)
    
    try:
        results = vector_index.query(
            vector=query_embedding,
            top_k=num_results,
            namespace=VECTOR_DB_NAMESPACE,  # CRITICAL: Company isolation
            include_metadata=True
        )
        
        matches = results.get("matches", [])
        if not matches:
            return "No relevant FAQ entries found in your company's knowledge base."
        
        context = "\n\n---\n\n".join([
            f"FAQ Entry {i+1}:\nQ: {match.get('metadata', {}).get('question', '')}\nA: {match.get('metadata', {}).get('answer', '')}"
            for i, match in enumerate(matches)
        ])
        
        return f"Found {len(matches)} detailed FAQ entries from {COMPANY_NAME}:\n\n{context}"
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"


tools = [search_faq, search_detailed_faq]

# Initialize the LLM
llm = init_chat_model(
    model="openai/gpt-oss-20b",
    model_provider="groq",
    api_key=GROQ_API_KEY
)

# System prompt with company isolation guardrails (knowledge injected here, not in memory)
# PLACEHOLDER values will be replaced with actual company data during deployment
system_prompt = """You are a helpful FAQ assistant for PLACEHOLDER_COMPANY_NAME (Company ID: PLACEHOLDER_COMPANY_ID).

CRITICAL DATA ISOLATION RULES:
1. You ONLY have access to PLACEHOLDER_COMPANY_NAME's knowledge base
2. You MUST ONLY respond with information from PLACEHOLDER_COMPANY_NAME's data
3. If asked about other companies or data you don't have, clearly state: "I only have access to PLACEHOLDER_COMPANY_NAME's information"
4. NEVER attempt to access or reference data from other companies
5. If a query seems to be about another company, politely redirect: "I can only help with PLACEHOLDER_COMPANY_NAME related questions"

Your goal is to answer user questions accurately using the available tools while maintaining strict data isolation.

Guidelines:
1. ALWAYS use the search_faq tool FIRST when answering any question - even if you think you know the answer
2. If the query is complex or the initial search doesn't provide enough information, use search_detailed_faq for more results
3. ALWAYS use the information returned by the search tools, even if the relevance scores seem low (scores > 0.2 are acceptable)
4. Provide clear, concise answers based on the retrieved information from the knowledge base
5. If the search tool returns results, USE THEM to answer the question - do not say you don't have the information
6. Only say "I don't have that information" if the search tool explicitly returns "No relevant FAQ entries found"
7. Never make up information or reference other companies

CRITICAL: You MUST call search_faq or search_detailed_faq for EVERY user question before responding. Do not skip this step.

When search_faq returns results with relevance scores, use those results to answer the question. Low scores (0.2-0.3) are still acceptable - use the information provided.

Think step-by-step and use tools strategically to provide the best answer while maintaining data isolation.

NOTE: This is a stateless agent. Each request is independent - no conversation history is maintained."""

# Create stateless agent (NO checkpointer, NO store, NO middleware for memory)
from langchain.agents import create_agent

agent = create_agent(
    model=llm,
    tools=tools,
    # NO checkpointer - stateless
    # NO store - stateless
    # NO middleware - stateless
    system_prompt=system_prompt,
)


# AgentCore Entrypoint (stateless - no memory context)
@app.entrypoint
def agent_invocation(payload, context):
    """Handler for stateless agent invocation in AgentCore runtime"""
    print(f"Stateless agent for {COMPANY_NAME} ({COMPANY_ID}) received payload:", payload)
    
    # Extract query from payload
    query = payload.get("prompt", "No prompt found in input")
    
    # Extract company_id from payload and verify it matches this agent's company
    payload_company_id = payload.get("company_id")
    if payload_company_id and payload_company_id != COMPANY_ID:
        return {
            "result": f"ERROR: Company ID mismatch. This agent belongs to {COMPANY_NAME} ({COMPANY_ID}), not company {payload_company_id}.",
            "error": "company_id_mismatch"
        }
    
    # Extract user info for logging (but NOT for memory/state)
    actor_id = payload.get("actor_id", payload.get("user_id", "default-user"))
    
    # Invoke the agent WITHOUT memory/state (stateless)
    try:
        # No config needed - agent is stateless
        result = agent.invoke(
            {"messages": [("human", query)]}
        )
        
        print("Result:", result)
        
        # Extract the final answer from the result
        messages = result.get("messages", [])
        answer = messages[-1].content if messages else "No response generated"
        
        # Return the answer (no state persisted)
        return {
            "result": answer,
            "company_id": COMPANY_ID,
            "company_name": COMPANY_NAME,
            "actor_id": actor_id,
            "stateless": True  # Indicate this is a stateless response
        }
    except Exception as e:
        print(f"Error invoking agent: {e}")
        return {
            "result": f"An error occurred while processing your request: {str(e)}",
            "error": str(e),
            "company_id": COMPANY_ID
        }


if __name__ == "__main__":
    app.run()
