# Dockerfile for stateless company agent runtime (Python 3.11)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Build arguments for company-specific configuration
ARG COMPANY_ID
ARG COMPANY_NAME
ARG VECTOR_DB_NAMESPACE

# Copy base runtime files
COPY runtime.py .

# Copy company-specific agent file (will be copied as company_agent_stateless.py before build)
# The build process copies the generated company_agent_${COMPANY_ID}_stateless.py 
# to company_agent_stateless.py before running docker build
COPY company_agent_stateless.py .

# Set build-time environment variables (for code generation/injection)
ENV COMPANY_ID=${COMPANY_ID}
ENV COMPANY_NAME=${COMPANY_NAME}
ENV VECTOR_DB_NAMESPACE=${VECTOR_DB_NAMESPACE}

# Runtime environment variables (will be overridden by AgentCore runtime)
ENV GROQ_API_KEY=""
ENV HF_API_KEY=""
ENV PINECONE_API_KEY=""
ENV PINECONE_INDEX_NAME="mcp-server"
ENV AWS_REGION=""

# Expose port (AgentCore runtime handles this)
EXPOSE 8080

# Run the stateless agent runtime
CMD ["python", "runtime.py"]
