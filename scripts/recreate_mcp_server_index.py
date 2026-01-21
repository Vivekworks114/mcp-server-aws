#!/usr/bin/env python3
"""
Recreate mcp-server index with 3072 dimensions for text-embedding-3-large
WARNING: This will delete all existing data in the index!
"""
import os
import sys
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv('backend/.env')

api_key = os.getenv("PINECONE_API_KEY", "pcsk_3HfNj9_CcJndVJC2PujGmnn8RNq1QhERWSdd9QFyCvyNuv7P9HWq8CRedGX4qj4cvgf2s7")
index_name = "mcp-server"

if not api_key:
    print("❌ PINECONE_API_KEY not set in backend/.env")
    sys.exit(1)

print("=" * 60)
print("RECREATING PINECONE INDEX")
print("=" * 60)
print(f"Index name: {index_name}")
print(f"Current dimension: 1024")
print(f"New dimension: 3072 (for text-embedding-3-large)")
print(f"\n⚠️  WARNING: This will DELETE all existing data in the index!")
print("=" * 60)

response = input("\nDo you want to continue? (yes/no): ")
if response.lower() != "yes":
    print("Cancelled.")
    sys.exit(0)

pc = Pinecone(api_key=api_key)

# Step 1: Delete existing index
print(f"\n[1/3] Deleting existing index '{index_name}'...")
try:
    pc.delete_index(index_name)
    print(f"✅ Index deleted successfully")
except Exception as e:
    error_msg = str(e).lower()
    if "not found" in error_msg or "does not exist" in error_msg:
        print(f"⚠️  Index doesn't exist (will create new one)")
    else:
        print(f"❌ Error: {e}")
        print(f"\nYou may need to delete it manually:")
        print(f"  1. Go to https://app.pinecone.io")
        print(f"  2. Find index '{index_name}'")
        print(f"  3. Delete it manually")
        print(f"  4. Then run this script again")
        sys.exit(1)

# Step 2: Wait for deletion to complete
print(f"\n[2/3] Waiting for deletion to complete (10 seconds)...")
for i in range(10, 0, -1):
    print(f"   {i}...", end='\r')
    time.sleep(1)
print("   Done!    ")

# Step 3: Create new index with 3072 dimensions
print(f"\n[3/3] Creating new index '{index_name}' with 3072 dimensions...")
try:
    pc.create_index(
        name=index_name,
        dimension=3072,  # Matches text-embedding-3-large
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
    print(f"✅ Index created successfully!")
except Exception as e:
    error_msg = str(e).lower()
    if "already exists" in error_msg:
        print(f"⚠️  Index still exists. Wait a bit longer and try again.")
        print(f"   Or delete it manually from Pinecone console")
    else:
        print(f"❌ Error creating index: {e}")
        sys.exit(1)

# Step 4: Verify
print(f"\n[Verification] Checking index...")
try:
    # Wait a moment for index to be ready
    time.sleep(3)
    
    index = pc.Index(index_name)
    stats = index.describe_index_stats()
    dimension = stats.get('dimension', 'unknown')
    
    print(f"✅ Index dimension: {dimension}")
    
    if dimension == 3072:
        print(f"\n" + "=" * 60)
        print(f"🎉 SUCCESS! Index is ready for text-embedding-3-large")
        print(f"=" * 60)
        print(f"\n📝 Next steps:")
        print(f"   1. Restart your backend server")
        print(f"   2. Try uploading knowledge base again")
        print(f"\n✅ The dimension mismatch should now be fixed!")
    else:
        print(f"⚠️  Warning: Index dimension is {dimension}, expected 3072")
        print(f"   The index may still be initializing. Wait a minute and check again.")
except Exception as e:
    print(f"⚠️  Could not verify index (may still be initializing): {e}")
    print(f"   Wait a minute and check with: python scripts/pine_test.py")
