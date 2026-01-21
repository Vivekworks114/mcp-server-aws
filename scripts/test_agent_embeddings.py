#!/usr/bin/env python3
"""
Test if the agent would use the same embeddings model as the backend
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv('backend/.env')

print("=" * 60)
print("Testing Embeddings Configuration")
print("=" * 60)

# Check backend configuration
print("\n📋 Backend Configuration:")
embeddings_provider = os.getenv("EMBEDDINGS_PROVIDER", "huggingface").lower()
embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "")
openai_api_key = os.getenv("OPENAI_API_KEY", "")

print(f"  EMBEDDINGS_PROVIDER: {embeddings_provider}")
print(f"  EMBEDDINGS_MODEL_NAME: {embeddings_model_name or '(not set)'}")
print(f"  OPENAI_API_KEY: {'✅ Set' if openai_api_key else '❌ Not set'}")

# Simulate backend logic
print("\n🔧 Backend Embeddings Selection:")
if embeddings_provider == "openai" or openai_api_key:
    try:
        from langchain_openai import OpenAIEmbeddings
        model_name = embeddings_model_name or "text-embedding-ada-002"
        print(f"  ✅ Using OpenAI: {model_name}")
        backend_emb = OpenAIEmbeddings(model=model_name, openai_api_key=openai_api_key)
        test_emb = backend_emb.embed_query("test")
        print(f"  ✅ Dimension: {len(test_emb)}")
        backend_dim = len(test_emb)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        backend_dim = None
else:
    from langchain_huggingface import HuggingFaceEmbeddings
    model_name = embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
    print(f"  ✅ Using HuggingFace: {model_name}")
    backend_emb = HuggingFaceEmbeddings(model_name=model_name)
    test_emb = backend_emb.embed_query("test")
    print(f"  ✅ Dimension: {len(test_emb)}")
    backend_dim = len(test_emb)

# Simulate agent logic (checking Secrets Manager)
print("\n🤖 Agent Configuration (simulated):")
print("  Note: Agent reads from AWS Secrets Manager at runtime")

# Check if OpenAI key would be available
try:
    import boto3
    secrets_client = boto3.client('secretsmanager', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    try:
        secret_response = secrets_client.get_secret_value(SecretId="agentcore/openai-api-key")
        agent_openai_key = secret_response.get("SecretString", "")
        print(f"  AWS Secret 'agentcore/openai-api-key': {'✅ Found' if agent_openai_key else '❌ Not found'}")
    except Exception as e:
        print(f"  AWS Secret 'agentcore/openai-api-key': ❌ Not found ({str(e)[:50]})")
        agent_openai_key = ""
except Exception as e:
    print(f"  ⚠️  Could not check AWS Secrets Manager: {e}")
    agent_openai_key = ""

# Agent would use environment variable or secret
agent_embeddings_provider = os.getenv("EMBEDDINGS_PROVIDER", "huggingface").lower()
agent_embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "")
agent_openai_key_env = os.getenv("OPENAI_API_KEY", "")

# Agent logic: use OpenAI if provider is "openai" OR if OpenAI key is available
if agent_embeddings_provider == "openai" or agent_openai_key_env or agent_openai_key:
    try:
        from langchain_openai import OpenAIEmbeddings
        OPENAI_AVAILABLE = True
    except ImportError:
        OPENAI_AVAILABLE = False
        print(f"  ⚠️  langchain-openai not available")
    
    if OPENAI_AVAILABLE and (agent_openai_key_env or agent_openai_key):
        model_name = agent_embeddings_model_name or "text-embedding-ada-002"
        print(f"  ✅ Agent would use OpenAI: {model_name}")
        agent_emb = OpenAIEmbeddings(
            model=model_name,
            openai_api_key=agent_openai_key_env or agent_openai_key
        )
        test_emb = agent_emb.embed_query("test")
        print(f"  ✅ Dimension: {len(test_emb)}")
        agent_dim = len(test_emb)
    else:
        print(f"  ⚠️  Agent would fallback to HuggingFace (OpenAI not available)")
        from langchain_huggingface import HuggingFaceEmbeddings
        model_name = agent_embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
        agent_emb = HuggingFaceEmbeddings(model_name=model_name)
        test_emb = agent_emb.embed_query("test")
        print(f"  ✅ Dimension: {len(test_emb)}")
        agent_dim = len(test_emb)
else:
    from langchain_huggingface import HuggingFaceEmbeddings
    model_name = agent_embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
    print(f"  ✅ Agent would use HuggingFace: {model_name}")
    agent_emb = HuggingFaceEmbeddings(model_name=model_name)
    test_emb = agent_emb.embed_query("test")
    print(f"  ✅ Dimension: {len(test_emb)}")
    agent_dim = len(test_emb)

# Compare
print("\n" + "=" * 60)
print("Comparison:")
print("=" * 60)
if backend_dim == agent_dim:
    print(f"✅ Dimensions match: {backend_dim}")
else:
    print(f"❌ Dimension mismatch!")
    print(f"   Backend: {backend_dim}")
    print(f"   Agent:   {agent_dim}")
    print(f"\n⚠️  This will cause search failures!")

# Check Pinecone index dimension
print("\n📊 Pinecone Index:")
try:
    from pinecone import Pinecone
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME", "mcp-server")
    if api_key:
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        index_dim = stats.get("dimension", "unknown")
        print(f"  Index: {index_name}")
        print(f"  Dimension: {index_dim}")
        
        if index_dim == backend_dim:
            print(f"  ✅ Index matches backend")
        else:
            print(f"  ❌ Index dimension ({index_dim}) doesn't match backend ({backend_dim})")
        
        if index_dim == agent_dim:
            print(f"  ✅ Index matches agent")
        else:
            print(f"  ❌ Index dimension ({index_dim}) doesn't match agent ({agent_dim})")
    else:
        print("  ⚠️  PINECONE_API_KEY not set")
except Exception as e:
    print(f"  ❌ Error checking Pinecone: {e}")

print("\n" + "=" * 60)
