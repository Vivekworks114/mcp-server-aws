"""Base template for company-specific agents with data isolation"""
import os
import uuid
from typing import List
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langgraph.store.base import BaseStore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langgraph_checkpoint_aws import AgentCoreMemorySaver, AgentCoreMemoryStore
from langchain.agents.middleware import AgentMiddleware, AgentState

# Get company-specific configuration from environment
COMPANY_ID = os.getenv("COMPANY_ID", "default-company")
COMPANY_NAME = os.getenv("COMPANY_NAME", "Default Company")
MEMORY_ID = os.getenv("MEMORY_ID", "default-memory")
VECTOR_DB_NAMESPACE = os.getenv("VECTOR_DB_NAMESPACE", f"company_{COMPANY_ID}")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY", "")

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Initialize memory components
checkpointer = AgentCoreMemorySaver(memory_id=MEMORY_ID)
store = AgentCoreMemoryStore(memory_id=MEMORY_ID)

# Initialize embeddings
emb = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
)

# Initialize vector database client
try:
    from pinecone import Pinecone
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", "mcp-server")
    
    if PINECONE_API_KEY:
        # Initialize Pinecone client (new SDK v5+)
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
    query_embedding = emb.embed_query(query)
    
    # Search only in company's namespace
    try:
        results = vector_index.query(
            vector=query_embedding,
            top_k=3,
            namespace=VECTOR_DB_NAMESPACE,  # CRITICAL: Company isolation
            include_metadata=True
        )
        
        # New SDK returns results as dict with 'matches' key
        matches = results.get("matches", [])
        if not matches:
            return "No relevant FAQ entries found in your company's knowledge base."
        
        context = "\n\n---\n\n".join([
            f"FAQ Entry {i+1}:\nQ: {match.get('metadata', {}).get('question', '')}\nA: {match.get('metadata', {}).get('answer', '')}"
            for i, match in enumerate(matches)
        ])
        
        return f"Found {len(matches)} relevant FAQ entries from {COMPANY_NAME}:\n\n{context}"
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"


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
        
        # New SDK returns results as dict with 'matches' key
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


class CompanyIsolationMiddleware(AgentMiddleware):
    """Middleware to enforce company data isolation"""
    
    def pre_model_hook(self, state: AgentState, config: RunnableConfig, *, store: BaseStore):
        """Hook that runs before LLM invocation to enforce company isolation"""
        actor_id = config["configurable"]["actor_id"]
        thread_id = config["configurable"]["thread_id"]
        
        # Namespace includes company_id for isolation: (company_id, actor_id, thread_id)
        namespace = (COMPANY_ID, actor_id, thread_id)
        messages = state.get("messages", [])
        
        # Save the last human message to long-term memory
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                store.put(namespace, str(uuid.uuid4()), {"message": msg})
                break
        
        return {"messages": messages}
    
    def post_model_hook(self, state: AgentState, config: RunnableConfig, *, store: BaseStore):
        """Hook that runs after LLM invocation to save AI responses"""
        actor_id = config["configurable"]["actor_id"]
        thread_id = config["configurable"]["thread_id"]
        namespace = (COMPANY_ID, actor_id, thread_id)
        
        messages = state.get("messages", [])
        
        # Save the last AI message
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                store.put(namespace, str(uuid.uuid4()), {"message": msg})
                break
        
        return state


# Initialize the LLM
llm = init_chat_model(
    model="openai/gpt-oss-20b",
    model_provider="groq",
    api_key=GROQ_API_KEY
)

# System prompt with company isolation guardrails
system_prompt = f"""You are a helpful FAQ assistant for {COMPANY_NAME} (Company ID: {COMPANY_ID}).

CRITICAL DATA ISOLATION RULES:
1. You ONLY have access to {COMPANY_NAME}'s knowledge base
2. You MUST ONLY respond with information from {COMPANY_NAME}'s data
3. If asked about other companies or data you don't have, clearly state: "I only have access to {COMPANY_NAME}'s information"
4. NEVER attempt to access or reference data from other companies
5. If a query seems to be about another company, politely redirect: "I can only help with {COMPANY_NAME} related questions"

Your goal is to answer user questions accurately using the available tools while maintaining strict data isolation.

Guidelines:
1. Use the search_faq tool to find relevant information from {COMPANY_NAME}'s knowledge base
2. If the query is complex, use search_detailed_faq for more results
3. Always provide clear, concise answers based on the retrieved information
4. If you cannot find relevant information, clearly state that you don't have that information in {COMPANY_NAME}'s knowledge base
5. Never make up information or reference other companies

Think step-by-step and use tools strategically to provide the best answer while maintaining data isolation."""

# Create the agent with memory configurations and isolation middleware
agent = create_agent(
    model=llm,
    tools=tools,
    checkpointer=checkpointer,
    store=store,
    middleware=[CompanyIsolationMiddleware()],
    system_prompt=system_prompt,
)


# AgentCore Entrypoint
@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation in AgentCore runtime with company isolation"""
    print(f"Agent for {COMPANY_NAME} ({COMPANY_ID}) received payload:", payload)
    print("Context:", context)
    
    # Extract query from payload
    query = payload.get("prompt", "No prompt found in input")
    
    # Extract company_id from payload and verify it matches this agent's company
    payload_company_id = payload.get("company_id")
    if payload_company_id and payload_company_id != COMPANY_ID:
        return {
            "result": f"ERROR: Company ID mismatch. This agent belongs to {COMPANY_NAME} ({COMPANY_ID}), not company {payload_company_id}.",
            "error": "company_id_mismatch"
        }
    
    # Extract or generate actor_id and thread_id
    actor_id = payload.get("actor_id", payload.get("user_id", "default-user"))
    thread_id = payload.get("thread_id", payload.get("session_id", "default-session"))
    
    # Configure memory context with company isolation
    config = {
        "configurable": {
            "thread_id": thread_id,
            "actor_id": actor_id,
            "company_id": COMPANY_ID  # Include company_id in config for isolation
        }
    }
    
    # Invoke the agent with memory
    try:
        result = agent.invoke(
            {"messages": [("human", query)]},
            config=config
        )
        
        print("Result:", result)
        
        # Extract the final answer from the result
        messages = result.get("messages", [])
        answer = messages[-1].content if messages else "No response generated"
        
        # Return the answer
        return {
            "result": answer,
            "company_id": COMPANY_ID,
            "company_name": COMPANY_NAME,
            "actor_id": actor_id,
            "thread_id": thread_id
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
