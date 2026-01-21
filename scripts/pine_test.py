#!/usr/bin/env python3
"""
Test Pinecone connection and check index dimension
Usage: python scripts/pine_test.py [index_name]
"""
import os
import sys
from pinecone import Pinecone
from dotenv import load_dotenv

# Load environment variables from backend/.env
load_dotenv('backend/.env')

api_key = os.getenv("PINECONE_API_KEY")
index_name = sys.argv[1] if len(sys.argv) > 1 else os.getenv("PINECONE_INDEX_NAME", "mcp-server")

if not api_key:
    print("❌ PINECONE_API_KEY not set in backend/.env")
    sys.exit(1)

print(f"Testing Pinecone connection...")
print(f"Index name: {index_name}")
print("-" * 60)

try:
    pc = Pinecone(api_key=api_key)
    
    # List all indexes
    indexes = pc.list_indexes()
    print(f"\nAvailable indexes:")
    for idx in indexes.indexes:
        print(f"  - {idx.name}")
    
    if index_name not in [idx.name for idx in indexes.indexes]:
        print(f"\n❌ Index '{index_name}' not found!")
        print(f"   Available indexes: {[idx.name for idx in indexes.indexes]}")
        sys.exit(1)
    
    # Connect to index
    index = pc.Index(index_name)
    stats = index.describe_index_stats()
    dimension = stats.get('dimension', 'unknown')
    
    print(f"\n✅ Connected successfully!")
    print(f"   Index: {index_name}")
    print(f"   Dimension: {dimension}")
    
    # Check if dimension matches expected
    expected_dim = os.getenv("EMBEDDINGS_MODEL_NAME", "")
    if "text-embedding-3-large" in expected_dim:
        expected_dim = 3072
    elif "text-embedding-ada-002" in expected_dim or "text-embedding-3-small" in expected_dim:
        expected_dim = 1536
    elif "all-MiniLM-L6-v2" in expected_dim:
        expected_dim = 384
    else:
        expected_dim = None
    
    if expected_dim:
        if dimension == expected_dim:
            print(f"   ✅ Dimension matches expected ({expected_dim})")
        else:
            print(f"   ⚠️  Dimension mismatch!")
            print(f"      Expected: {expected_dim} (for {os.getenv('EMBEDDINGS_MODEL_NAME', 'current model')})")
            print(f"      Actual: {dimension}")
            print(f"   💡 Fix: Create new index with correct dimension")
            print(f"      python scripts/create_pinecone_index_3072.py {index_name} --delete")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)