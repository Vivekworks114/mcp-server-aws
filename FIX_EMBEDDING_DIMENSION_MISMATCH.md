# Fix Embedding Dimension Mismatch

## Problem

You're getting an error:
```
Vector dimension 384 does not match the dimension of the index 1024
```

This means:
- Your embeddings model produces **384-dimensional** vectors
- Your Pinecone index expects **1024-dimensional** vectors

## Solutions

### Option 1: Use a Model That Produces 1024 Dimensions (Recommended)

Update your `.env` file to use a model that produces 1024 dimensions:

```bash
# In backend/.env
EMBEDDINGS_MODEL_NAME=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
```

**Note**: Most sentence-transformers models produce 384 or 768 dimensions, not 1024. You may need to:
- Use OpenAI embeddings (requires API key)
- Use a custom model that produces 1024 dimensions
- Or use Option 2 below

### Option 2: Recreate Pinecone Index with 384 Dimensions (Easier)

If you can recreate your Pinecone index, create it with 384 dimensions to match the default model:

1. **Delete the existing index** (if possible, or create a new one with a different name)

2. **Create a new index with 384 dimensions**:

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="your-api-key")

pc.create_index(
    name="mcp-server",  # or your index name
    dimension=384,  # Match the embeddings model dimension
    metric="cosine",
    spec=ServerlessSpec(
        cloud="aws",
        region="us-east-1"
    )
)
```

3. **Update your `.env`**:

```bash
PINECONE_INDEX_NAME=mcp-server  # Your new index name
EMBEDDINGS_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2  # 384 dimensions
```

### Option 3: Use OpenAI Embeddings (If You Have API Key) ✅ **NOW IMPLEMENTED!**

If you have an OpenAI API key, you can use their embeddings which produce 1536 dimensions. **The code now supports this automatically!**

1. **Install the OpenAI package**:

```bash
pip install langchain-openai
```

Or update requirements:
```bash
pip install -r requirements.txt
```

2. **Update your Pinecone index to 1536 dimensions** (or create a new one):

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="your-pinecone-api-key")

pc.create_index(
    name="mcp-server-openai",  # New index name
    dimension=1536,  # OpenAI embeddings dimension
    metric="cosine",
    spec=ServerlessSpec(
        cloud="aws",
        region="us-east-1"
    )
)
```

3. **Update your `.env` file**:

```bash
# In backend/.env
EMBEDDINGS_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key-here
PINECONE_INDEX_NAME=mcp-server-openai  # Your 1536-dimension index
```

4. **Restart your backend server** - That's it! The code will automatically use OpenAI embeddings.

**Note**: The agent code will also automatically use OpenAI embeddings if `OPENAI_API_KEY` is set, or if `EMBEDDINGS_PROVIDER=openai` is configured.

## Current Configuration

### Default Model
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Location**: Used in both backend and agent code

### Your Pinecone Index
- **Index Name**: `mcp-server` (or check your `.env`)
- **Dimensions**: 1024 (from the error message)
- **Mismatch**: Yes - 384 ≠ 1024

## Quick Fix (Recommended)

**Easiest solution**: Recreate your Pinecone index with 384 dimensions:

```bash
# 1. Update backend/.env
EMBEDDINGS_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2

# 2. Create new Pinecone index with 384 dimensions (see Python code above)

# 3. Restart backend server
```

## Verification

After fixing, test the upload:

```bash
# Try uploading knowledge base again via Admin Panel
# Should work without dimension mismatch error
```

## Models and Their Dimensions

| Model | Dimensions |
|-------|------------|
| `sentence-transformers/all-MiniLM-L6-v2` | 384 |
| `sentence-transformers/all-mpnet-base-v2` | 768 |
| `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | 768 |
| `text-embedding-ada-002` (OpenAI) | 1536 |
| `text-embedding-3-small` (OpenAI) | 1536 |
| `text-embedding-3-large` (OpenAI) | 3072 |

## Important Notes

1. **Both backend and agent must use the same model** - They're both updated to use `EMBEDDINGS_MODEL_NAME` environment variable
2. **Pinecone index dimension is fixed** - Once created, you can't change it (must recreate)
3. **All vectors in the index must have the same dimension** - Can't mix different dimensions
