#!/usr/bin/env python3
"""
Create Pinecone index with 3072 dimensions for text-embedding-3-large
Usage: python scripts/create_pinecone_index_3072.py [index_name]
"""
import os
import sys
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

# Load environment variables
load_dotenv('backend/.env')

api_key = os.getenv("PINECONE_API_KEY")
if not api_key:
    print("❌ PINECONE_API_KEY not set in backend/.env")
    sys.exit(1)

# Get index name from command line or env
index_name = sys.argv[1] if len(sys.argv) > 1 else os.getenv("PINECONE_INDEX_NAME", "mcp-server")

print(f"Creating Pinecone index: {index_name}")
print(f"Dimension: 3072 (for text-embedding-3-large)")
print("-" * 60)

pc = Pinecone(api_key=api_key)

# Check if index already exists
try:
    existing_indexes = pc.list_indexes()
    index_names = [idx.name for idx in existing_indexes.indexes]
    
    if index_name in index_names:
        print(f"⚠️  Index '{index_name}' already exists!")
        
        # Check its dimension
        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        current_dim = stats.get('dimension', 'unknown')
        
        print(f"   Current dimension: {current_dim}")
        
        if current_dim == 3072:
            print(f"✅ Index already has correct dimension (3072)")
            print(f"   No action needed!")
            sys.exit(0)
        else:
            print(f"❌ Index has wrong dimension ({current_dim}, need 3072)")
            print(f"\nOptions:")
            print(f"  1. Delete and recreate: python scripts/create_pinecone_index_3072.py {index_name} --delete")
            print(f"  2. Create new index with different name: python scripts/create_pinecone_index_3072.py mcp-server-3072")
            sys.exit(1)
except Exception as e:
    print(f"Error checking existing indexes: {e}")

# Delete existing index if --delete flag is set
if "--delete" in sys.argv:
    try:
        print(f"\n🗑️  Deleting existing index '{index_name}'...")
        pc.delete_index(index_name)
        print(f"✅ Deleted index '{index_name}'")
    except Exception as e:
        print(f"⚠️  Could not delete index: {e}")

# Create new index
try:
    print(f"\n🚀 Creating index '{index_name}' with 3072 dimensions...")
    pc.create_index(
        name=index_name,
        dimension=3072,  # Matches text-embedding-3-large
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"  # Change if needed
        )
    )
    print(f"✅ Successfully created index '{index_name}' with 3072 dimensions!")
    
    # Verify
    print(f"\n🔍 Verifying index...")
    index = pc.Index(index_name)
    stats = index.describe_index_stats()
    print(f"✅ Index dimension: {stats.get('dimension')}")
    print(f"✅ Index ready for use!")
    
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"⚠️  Index '{index_name}' already exists")
        print(f"   Use --delete flag to recreate it")
    else:
        print(f"❌ Error creating index: {e}")
        sys.exit(1)

print(f"\n📝 Next steps:")
print(f"   1. Update backend/.env: PINECONE_INDEX_NAME={index_name}")
print(f"   2. Restart backend server")
print(f"   3. Try uploading knowledge base again")
