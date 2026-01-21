#!/usr/bin/env python3
"""
Set the embeddings model name in AWS Secrets Manager
This ensures the agent uses the same embeddings model as the backend
"""
import os
import sys
import boto3
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv('backend/.env')

def main():
    # Get embeddings model name from backend .env
    embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "")
    embeddings_provider = os.getenv("EMBEDDINGS_PROVIDER", "huggingface").lower()
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    
    print("=" * 70)
    print("Setting Embeddings Model Name in AWS Secrets Manager")
    print("=" * 70)
    
    # Determine what model should be used
    if embeddings_provider == "openai" or openai_api_key:
        if not embeddings_model_name:
            # Default OpenAI model
            embeddings_model_name = "text-embedding-ada-002"
            print(f"\n⚠️  EMBEDDINGS_MODEL_NAME not set in backend/.env")
            print(f"   Will use default: {embeddings_model_name}")
        else:
            print(f"\n✅ Found EMBEDDINGS_MODEL_NAME: {embeddings_model_name}")
    else:
        if not embeddings_model_name:
            embeddings_model_name = "sentence-transformers/all-MiniLM-L6-v2"
            print(f"\n⚠️  EMBEDDINGS_MODEL_NAME not set in backend/.env")
            print(f"   Will use default HuggingFace: {embeddings_model_name}")
        else:
            print(f"\n✅ Found EMBEDDINGS_MODEL_NAME: {embeddings_model_name}")
    
    # Get dimension for the model
    print(f"\n📊 Model Information:")
    if "text-embedding-3-large" in embeddings_model_name:
        dimension = 3072
        print(f"   Model: {embeddings_model_name}")
        print(f"   Dimension: {dimension}")
    elif "text-embedding" in embeddings_model_name or "ada-002" in embeddings_model_name:
        dimension = 1536
        print(f"   Model: {embeddings_model_name}")
        print(f"   Dimension: {dimension}")
    elif "all-MiniLM" in embeddings_model_name:
        dimension = 384
        print(f"   Model: {embeddings_model_name}")
        print(f"   Dimension: {dimension}")
    else:
        dimension = "unknown"
        print(f"   Model: {embeddings_model_name}")
        print(f"   Dimension: {dimension} (please verify)")
    
    # Store in Secrets Manager
    region = os.getenv("AWS_REGION", "us-east-1")
    secrets_client = boto3.client("secretsmanager", region_name=region)
    
    secret_name = "agentcore/embeddings-model-name"
    
    try:
        # Try to update existing secret
        secrets_client.update_secret(
            SecretId=secret_name,
            SecretString=embeddings_model_name
        )
        print(f"\n✅ Updated secret '{secret_name}' with value: {embeddings_model_name}")
    except secrets_client.exceptions.ResourceNotFoundException:
        # Secret doesn't exist, create it
        try:
            secrets_client.create_secret(
                Name=secret_name,
                SecretString=embeddings_model_name,
                Description="Embeddings model name for agent runtime (must match backend configuration)"
            )
            print(f"\n✅ Created secret '{secret_name}' with value: {embeddings_model_name}")
        except Exception as e:
            print(f"\n❌ Failed to create secret: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Failed to update secret: {e}")
        sys.exit(1)
    
    # Verify
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        stored_value = response["SecretString"]
        print(f"\n✅ Verified: Secret '{secret_name}' = '{stored_value}'")
    except Exception as e:
        print(f"\n⚠️  Could not verify secret: {e}")
    
    print("\n" + "=" * 70)
    print("Next Steps:")
    print("=" * 70)
    print("1. Redeploy your agent to use the updated embeddings model")
    print("2. The agent will now read this value from Secrets Manager")
    print("3. Ensure your Pinecone index dimension matches the model dimension")
    if dimension == 3072:
        print(f"\n⚠️  IMPORTANT: Your Pinecone index must be {dimension} dimensions")
        print("   If it's not, run: python scripts/recreate_mcp_server_index.py")
    print()

if __name__ == "__main__":
    main()
