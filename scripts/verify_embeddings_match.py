#!/usr/bin/env python3
"""
Verify that backend and agent use the same embeddings model
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv('backend/.env')

print("=" * 70)
print("Embeddings Configuration Verification")
print("=" * 70)

# Check backend configuration
print("\n📋 Backend Configuration:")
embeddings_provider = os.getenv("EMBEDDINGS_PROVIDER", "huggingface").lower()
embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "")
openai_api_key = os.getenv("OPENAI_API_KEY", "")

print(f"  EMBEDDINGS_PROVIDER: {embeddings_provider}")
print(f"  EMBEDDINGS_MODEL_NAME: {embeddings_model_name or '(not set - will use default)'}")
print(f"  OPENAI_API_KEY: {'✅ Set' if openai_api_key else '❌ Not set'}")

# Determine what backend would use
print("\n🔧 Backend Embeddings Model:")
backend_model = None
backend_dim = None

if embeddings_provider == "openai" or openai_api_key:
    try:
        from langchain_openai import OpenAIEmbeddings
        model_name = embeddings_model_name or "text-embedding-ada-002"
        print(f"  ✅ Would use: OpenAI - {model_name}")
        backend_emb = OpenAIEmbeddings(model=model_name, openai_api_key=openai_api_key)
        test_emb = backend_emb.embed_query("test")
        backend_dim = len(test_emb)
        backend_model = model_name
        print(f"  ✅ Dimension: {backend_dim}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        backend_dim = None
else:
    from langchain_huggingface import HuggingFaceEmbeddings
    model_name = embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
    print(f"  ✅ Would use: HuggingFace - {model_name}")
    backend_emb = HuggingFaceEmbeddings(model_name=model_name)
    test_emb = backend_emb.embed_query("test")
    backend_dim = len(test_emb)
    backend_model = model_name
    print(f"  ✅ Dimension: {backend_dim}")

# Check what agent would use (from Secrets Manager)
print("\n🤖 Agent Configuration (from AWS Secrets Manager):")
try:
    import boto3
    secrets_client = boto3.client('secretsmanager', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    
    # Check OpenAI key
    try:
        secret_response = secrets_client.get_secret_value(SecretId="agentcore/openai-api-key")
        agent_openai_key = secret_response.get("SecretString", "")
        print(f"  AWS Secret 'agentcore/openai-api-key': {'✅ Found' if agent_openai_key else '❌ Empty'}")
    except Exception as e:
        print(f"  AWS Secret 'agentcore/openai-api-key': ❌ Not found")
        print(f"    Error: {str(e)[:80]}")
        agent_openai_key = ""
    
    # Agent would check environment variables first, then secrets
    agent_embeddings_provider = os.getenv("EMBEDDINGS_PROVIDER", "huggingface").lower()
    agent_embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "")
    agent_openai_key_env = os.getenv("OPENAI_API_KEY", "")
    
    # Determine what agent would use
    print("\n🔧 Agent Embeddings Model:")
    agent_model = None
    agent_dim = None
    
    if agent_embeddings_provider == "openai" or agent_openai_key_env or agent_openai_key:
        try:
            from langchain_openai import OpenAIEmbeddings
            OPENAI_AVAILABLE = True
        except ImportError:
            OPENAI_AVAILABLE = False
            print(f"  ⚠️  langchain-openai not available in this environment")
        
        if OPENAI_AVAILABLE and (agent_openai_key_env or agent_openai_key):
            model_name = agent_embeddings_model_name or "text-embedding-ada-002"
            print(f"  ✅ Would use: OpenAI - {model_name}")
            agent_emb = OpenAIEmbeddings(
                model=model_name,
                openai_api_key=agent_openai_key_env or agent_openai_key
            )
            test_emb = agent_emb.embed_query("test")
            agent_dim = len(test_emb)
            agent_model = model_name
            print(f"  ✅ Dimension: {agent_dim}")
        else:
            print(f"  ⚠️  Would fallback to HuggingFace (OpenAI not available)")
            from langchain_huggingface import HuggingFaceEmbeddings
            model_name = agent_embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
            agent_emb = HuggingFaceEmbeddings(model_name=model_name)
            test_emb = agent_emb.embed_query("test")
            agent_dim = len(test_emb)
            agent_model = model_name
            print(f"  ✅ Dimension: {agent_dim}")
    else:
        from langchain_huggingface import HuggingFaceEmbeddings
        model_name = agent_embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
        print(f"  ✅ Would use: HuggingFace - {model_name}")
        agent_emb = HuggingFaceEmbeddings(model_name=model_name)
        test_emb = agent_emb.embed_query("test")
        agent_dim = len(test_emb)
        agent_model = model_name
        print(f"  ✅ Dimension: {agent_dim}")
    
except Exception as e:
    print(f"  ❌ Error checking AWS Secrets Manager: {e}")
    agent_dim = None
    agent_model = None

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
    else:
        print("  ⚠️  PINECONE_API_KEY not set")
        index_dim = None
except Exception as e:
    print(f"  ❌ Error: {e}")
    index_dim = None

# Summary
print("\n" + "=" * 70)
print("Summary:")
print("=" * 70)

if backend_dim and agent_dim:
    if backend_dim == agent_dim == index_dim:
        print(f"✅ PERFECT MATCH!")
        print(f"   Backend: {backend_model} ({backend_dim} dims)")
        print(f"   Agent:   {agent_model} ({agent_dim} dims)")
        print(f"   Index:   {index_dim} dims")
        print(f"\n✅ All embeddings configurations match!")
    elif backend_dim == agent_dim:
        print(f"⚠️  Backend and Agent match, but Index differs:")
        print(f"   Backend: {backend_model} ({backend_dim} dims)")
        print(f"   Agent:   {agent_model} ({agent_dim} dims)")
        print(f"   Index:   {index_dim} dims")
        print(f"\n❌ Index dimension mismatch! This will cause search failures.")
    elif backend_dim == index_dim:
        print(f"⚠️  Backend and Index match, but Agent differs:")
        print(f"   Backend: {backend_model} ({backend_dim} dims)")
        print(f"   Agent:   {agent_model} ({agent_dim} dims)")
        print(f"   Index:   {index_dim} dims")
        print(f"\n❌ Agent embeddings mismatch! Agent will produce wrong embeddings.")
    else:
        print(f"❌ MISMATCH DETECTED:")
        print(f"   Backend: {backend_model} ({backend_dim} dims)")
        print(f"   Agent:   {agent_model} ({agent_dim} dims)")
        print(f"   Index:   {index_dim} dims")
        print(f"\n❌ Multiple mismatches detected!")
else:
    print(f"⚠️  Could not determine all configurations")

print("\n" + "=" * 70)
print("Recommendations:")
print("=" * 70)

if backend_dim and agent_dim and backend_dim != agent_dim:
    print(f"\n1. Ensure agent uses same embeddings model as backend:")
    print(f"   - Set EMBEDDINGS_MODEL_NAME={backend_model} in agent environment")
    print(f"   - Or ensure 'agentcore/openai-api-key' secret contains valid OpenAI API key")
    print(f"   - Redeploy agent after fixing")

if backend_dim and index_dim and backend_dim != index_dim:
    print(f"\n2. Fix Pinecone index dimension:")
    print(f"   - Current index: {index_dim} dimensions")
    print(f"   - Required: {backend_dim} dimensions")
    print(f"   - Run: python scripts/recreate_mcp_server_index.py")
    print(f"   - Or recreate index manually with {backend_dim} dimensions")

if backend_dim == agent_dim == index_dim:
    print(f"\n✅ Configuration is correct!")
    print(f"   If search still fails, the issue might be:")
    print(f"   - Low quality embeddings (try a different model)")
    print(f"   - Poor query/question matching")
    print(f"   - Agent not calling search_faq tool")

print()
