# Quick Start Guide

Get up and running with the Multi-Company Agent System in minutes.

## Prerequisites

- Python 3.13+
- pip (comes with Python)
- Node.js 18+
- AWS Account (for production)

## Step 1: Clone Repository

```bash
cd /path/to/your/projects
git clone <repository-url>
cd agentcore-crash-course-main
```

## Step 2: Set Up Python Environment

### Option A: Using Setup Script (Recommended)

**macOS/Linux:**
```bash
./scripts/setup_venv.sh
```

**Windows:**
```bash
scripts\setup_venv.bat
```

### Option B: Manual Setup

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# macOS/Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Configure Environment Variables

```bash
# Backend
cp backend/env.example backend/.env
# Edit backend/.env with your values

# Admin Panel
cp frontend/admin-panel/env.example frontend/admin-panel/.env.local
# Edit frontend/admin-panel/.env.local

# Company Panel
cp frontend/company-panel/env.example frontend/company-panel/.env.local
# Edit frontend/company-panel/.env.local
```

## Step 4: Set Up AWS (For Production)

See `AWS_SETUP_GUIDE.md` for detailed instructions.

Quick setup:
```bash
# Create DynamoDB tables
./scripts/create_dynamodb_tables.sh us-east-1

# Set up secrets
./scripts/setup_secrets.sh us-east-1
```

## Step 5: Run Backend

### Option A: Using Run Script (Recommended)

```bash
# Make sure virtual environment is activated
source .venv/bin/activate  # macOS/Linux

# Run backend using script
./scripts/run_backend_simple.sh
```

### Option B: Manual Run

```bash
# Make sure virtual environment is activated
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Run backend from backend directory
cd backend
uvicorn main:app --reload --port 8000
```

**Note**: The `main.py` file automatically handles Python path configuration, so you can run it from the `backend` directory directly.

Backend will be available at: `http://localhost:8000`
API docs will be available at: `http://localhost:8000/docs`

## Step 6: Run Frontend Applications

### Admin Panel

Open a new terminal:
```bash
cd frontend/admin-panel
npm install
npm run dev
```

Admin Panel will be available at: `http://localhost:3000`

### Company Panel

Open another terminal:
```bash
cd frontend/company-panel
npm install
npm run dev
```

Company Panel will be available at: `http://localhost:3001`

## Step 7: Test the System

1. **Access Admin Panel**: `http://localhost:3000`
2. **Login** with admin credentials (create first admin via backend or database)
3. **Create a Company** via Admin Panel
4. **Upload Knowledge Base** for the company
5. **Access Company Panel**: `http://localhost:3001`
6. **Login** as company employee
7. **Chat** with the company's agent

## Troubleshooting

### Virtual Environment Issues

```bash
# If activation fails, recreate virtual environment
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Port Already in Use

```bash
# Backend (change port)
uvicorn main:app --reload --port 8001

# Frontend (change in package.json scripts)
# Or kill process using the port
lsof -ti:8000 | xargs kill  # macOS/Linux
```

### Missing Dependencies

```bash
# Reinstall all dependencies
pip install --upgrade -r requirements.txt
```

## Next Steps

- Read `README_IMPLEMENTATION.md` for detailed documentation
- Follow `AWS_SETUP_GUIDE.md` for production deployment
- Check `README_ENV_SETUP.md` for environment variable details
