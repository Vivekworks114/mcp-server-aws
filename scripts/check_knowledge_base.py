#!/usr/bin/env python3
"""
Check knowledge base data in Pinecone for a company
Usage: python scripts/check_knowledge_base.py <company_id>
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv('backend/.env')

from backend.database import db
from pinecone import Pinecone

if len(sys.argv) < 2:
    print("Usage: python scripts/check_knowledge_base.py <company_id>")
    sys.exit(1)

company_id = sys.argv[1]

print(f"Checking knowledge base for company: {company_id}")
print("-" * 60)

# Get company info
company = db.get_company(company_id)
if not company:
    print(f"❌ Company not found: {company_id}")
    sys.exit(1)

namespace = company.get("vector_db_namespace", f"company_{company_id}")
print(f"✅ Company: {company.get('name')}")
print(f"   Namespace: {namespace}")

# Connect to Pinecone
api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX_NAME", "mcp-server")

if not api_key:
    print("❌ PINECONE_API_KEY not set")
    sys.exit(1)

try:
    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    
    # Get namespace stats
    stats = index.describe_index_stats()
    namespaces = stats.get("namespaces", {})
    
    print(f"\n📊 Pinecone Index: {index_name}")
    print(f"   Total namespaces: {len(namespaces)}")
    
    if namespace in namespaces:
        ns_stats = namespaces[namespace]
        vector_count = ns_stats.get("vector_count", 0)
        print(f"\n✅ Namespace '{namespace}' found!")
        print(f"   Vector count: {vector_count}")
        
        if vector_count == 0:
            print(f"\n⚠️  WARNING: No vectors found in namespace!")
            print(f"   The knowledge base may not have been uploaded correctly.")
        else:
            print(f"\n✅ Knowledge base has {vector_count} entries")
            
            # Try a sample query
            print(f"\n🔍 Testing search...")
            from backend.routes.admin import HuggingFaceEmbeddings, OpenAIEmbeddings
            import os
            
            # Use same embeddings as backend
            embeddings_provider = os.getenv("EMBEDDINGS_PROVIDER", "huggingface").lower()
            embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "")
            openai_api_key = os.getenv("OPENAI_API_KEY", "")
            
            if embeddings_provider == "openai" or openai_api_key:
                try:
                    from langchain_openai import OpenAIEmbeddings
                    model_name = embeddings_model_name or "text-embedding-ada-002"
                    emb_model = OpenAIEmbeddings(model=model_name, openai_api_key=openai_api_key)
                except:
                    from langchain_huggingface import HuggingFaceEmbeddings
                    emb_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            else:
                from langchain_huggingface import HuggingFaceEmbeddings
                model_name = embeddings_model_name or "sentence-transformers/all-MiniLM-L6-v2"
                emb_model = HuggingFaceEmbeddings(model_name=model_name)
            
            test_query = "What are your business hours?"
            query_embedding = emb_model.embed_query(test_query)
            
            results = index.query(
                vector=query_embedding,
                top_k=3,
                namespace=namespace,
                include_metadata=True
            )
            
            matches = results.get("matches", [])
            print(f"   Query: '{test_query}'")
            print(f"   Found {len(matches)} matches:")
            for i, match in enumerate(matches, 1):
                metadata = match.get("metadata", {})
                print(f"   {i}. Score: {match.get('score', 0):.4f}")
                print(f"      Q: {metadata.get('question', 'N/A')}")
                print(f"      A: {metadata.get('answer', 'N/A')[:100]}...")
    else:
        print(f"\n❌ Namespace '{namespace}' not found in index!")
        print(f"\nAvailable namespaces:")
        for ns_name, ns_stats in namespaces.items():
            print(f"   - {ns_name}: {ns_stats.get('vector_count', 0)} vectors")
        
        print(f"\n💡 Possible issues:")
        print(f"   1. Knowledge base was uploaded to wrong namespace")
        print(f"   2. Knowledge base upload failed")
        print(f"   3. Namespace name mismatch")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
