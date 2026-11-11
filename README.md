# Student Grade Management System

A single-institution grade management system for BITS College. The project is built as a React frontend and a FastAPI backend.

## Requirements

- Node.js 20+
- Python 3.11+

## Run the API

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; its initial health check is `http://localhost:8000/api/health`.

## Run the frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite runs at `http://localhost:5173` and proxies `/api` requests to the local FastAPI server.

## Checks

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest
```

```powershell
cd frontend
npm run build
```

Domain terms and grade concepts are documented in [GLOSSARY.md](./GLOSSARY.md).
