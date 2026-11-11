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

Create an initial administrator account in another terminal from `backend/`:

```powershell
python -m app.create_user --email admin@bitscollege.edu.et --name "Academic Administrator" --role admin
```

The command prompts for a password and requires at least 12 characters. For production, set `SGMS_COOKIE_SECURE=true` so the session cookie is sent only over HTTPS.

The starter grade scale is `A` (90%), `B` (80%), `C` (70%), `D` (60%), and `F` (0%). An administrator can replace it through `PUT /api/grade-scale`; confirm BITS College's official thresholds before using the starter scale for academic decisions.

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
