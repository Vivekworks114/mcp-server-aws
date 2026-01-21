# OpenAI Embeddings Setup Guide

## Quick Start

If you have an OpenAI API key and want to use OpenAI embeddings (1536 dimensions), follow these steps:

### 1. Install Dependencies

```bash
pip install langchain-openai
```

Or update all requirements:
```bash
pip install -r requirements.txt
```

### 2. Create Pinecone Index with 1536 Dimensions

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="your-pinecone-api-key")

# Create index with 1536 dimensions (matches OpenAI embeddings)
pc.create_index(
    name="mcp-server-openai",
    dimension=1536,
    metric="cosine",
    spec=ServerlessSpec(
        cloud="aws",
        region="us-east-1"  # Change to your region
    )
)
```

### 3. Update Environment Variables

**Backend `.env` file** (`backend/.env`):

```bash
# Use OpenAI embeddings
EMBEDDINGS_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-api-key-here
PINECONE_INDEX_NAME=mcp-server-openai

# Optional: specify model (default is text-embedding-ada-002)
EMBEDDINGS_MODEL_NAME=text-embedding-ada-002
```

**For Agent Deployment** (AWS Secrets Manager or environment):

The agent will automatically use OpenAI embeddings if:
- `OPENAI_API_KEY` is set in environment, OR
- `EMBEDDINGS_PROVIDER=openai` is set, OR
- The secret `agentcore/openai-api-key` exists in AWS Secrets Manager

### 4. Restart Backend Server

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 5. Test Knowledge Base Upload

Try uploading knowledge base data via Admin Panel - it should now work with 1536-dimensional vectors!

## How It Works

The code automatically detects which embeddings provider to use:

1. **If `OPENAI_API_KEY` is set** → Uses OpenAI embeddings (1536 dims)
2. **If `EMBEDDINGS_PROVIDER=openai`** → Uses OpenAI embeddings
3. **Otherwise** → Uses HuggingFace embeddings (384 dims by default)

Both backend and agent code use the same logic, so they'll always match.

## OpenAI Embedding Models

| Model | Dimensions | Cost (per 1M tokens) |
|-------|------------|----------------------|
| `text-embedding-ada-002` | 1536 | $0.10 |
| `text-embedding-3-small` | 1536 | $0.02 |
| `text-embedding-3-large` | 3072 | $0.13 |

**Default**: `text-embedding-ada-002` (1536 dimensions)

## Benefits of OpenAI Embeddings

1. **Higher Quality**: Generally better semantic understanding
2. **Consistent Dimensions**: Always 1536 (or 3072 for large)
3. **No Local Model Loading**: Faster startup, no GPU needed
4. **Better Multilingual Support**: Especially with ada-002

## Troubleshooting

### Error: "langchain_openai not found"
```bash
pip install langchain-openai
```

### Error: "OPENAI_API_KEY is required"
Make sure you've set `OPENAI_API_KEY` in your `.env` file.

### Error: "Vector dimension 1536 does not match..."
Your Pinecone index dimension doesn't match. Either:
- Create a new index with 1536 dimensions (see step 2 above)
- Or switch back to HuggingFace embeddings (384 dimensions)

### Agent Not Using OpenAI Embeddings

Check that the agent has access to `OPENAI_API_KEY`:
- If deployed: Ensure secret `agentcore/openai-api-key` exists in AWS Secrets Manager
- If local: Set `OPENAI_API_KEY` environment variable

## Switching Back to HuggingFace

If you want to switch back to HuggingFace embeddings:

```bash
# In backend/.env
EMBEDDINGS_PROVIDER=huggingface
# Remove or comment out OPENAI_API_KEY
# OPENAI_API_KEY=
```

Then restart the backend server.
