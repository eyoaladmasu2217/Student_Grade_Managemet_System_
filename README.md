# Student Grade Management System

A single-institution grade management system for BITS College. The project is built as a React frontend and a FastAPI backend.

## Requirements

- Node.js 20.19+ or 22.12+
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
The interactive API reference is available at `http://localhost:8000/docs`. SQLite data is stored in `backend/data/gradebook.sqlite3` by default; set `SGMS_DATABASE_PATH` to use another file.

Create an initial administrator account in another terminal from `backend/`:

```powershell
python -m app.create_user --email admin@bitscollege.edu.et --name "Academic Administrator" --role admin
```

The command prompts for a password and requires at least 12 characters. For production, set `SGMS_COOKIE_SECURE=true` so the session cookie is sent only over HTTPS.

The starter grade scale is `A` (90%), `B` (80%), `C` (70%), `D` (60%), and `F` (0%). An administrator can replace it through `PUT /api/grade-scale`; confirm BITS College's official thresholds before using the starter scale for academic decisions.

An instructor can release grades only after every active student has a score for every assessment and category weights total 100%. Unreleased work is treated as ungraded; it does not count as zero. After release, assessment structure is locked.

Released-grade corrections require a reason code and an explanation. Instructor submissions create a pending request without changing the student's score; an administrator approves and applies the change or rejects it with a note. Direct administrator corrections are approved immediately. Every request, approval, and rejection is recorded in the section's append-only audit trail, and instructors can see request status in their correction history.

Students can use the private What-If simulator on their dashboard to replace hypothetical scores and see the resulting weighted grade. The endpoint exposes assessment structure and grade bands but hides personal scores until grades are released. The simulator never writes grades.

For deployments where the browser calls the API from a different origin, set `SGMS_FRONTEND_ORIGINS` to a comma-separated allowlist. Wildcards and relative URLs are rejected. See [.env.example](./.env.example) for every supported setting.

## Production security checklist

- Set `SGMS_ENV=production`. This hides `/docs`, `/redoc`, and `/openapi.json`, and prevents `SGMS_COOKIE_SECURE=false` from taking effect.
- Terminate HTTPS and set `SGMS_COOKIE_SECURE=true`. `SGMS_ALLOW_INSECURE_COOKIES` is intended only for local development over plain HTTP.
- Keep `SGMS_FRONTEND_ORIGINS` as an exact allowlist. The API additionally rejects cross-site state-changing requests that carry an untrusted `Origin` or `Sec-Fetch-Site` header, and browser writes must include `X-Requested-With: XMLHttpRequest` (the frontend does this automatically).
- Failed sign-ins are throttled per account across all client addresses and per address; security events are written to the `sgms.security` logger, so configure your log collector to retain them.
- Sign-in rotates the presented session token, and oversized session tokens are rejected before they are hashed. Sessions expire after 12 hours or two hours of inactivity. Use `POST /api/auth/logout-all` to revoke every session for the current account, and `PATCH /api/users/{id}/active` to disable an account during incident response.
- Request bodies are capped by `SGMS_MAX_REQUEST_BYTES` (1 MiB by default). Rejected writes, permission denials, and oversized bodies are logged as security events.
- Grade-change audit events are immutable at the database level, and the SQLite database directory and files are created with owner-only permissions.
- Always create accounts with passwords of at least 12 characters that are not common, sequential, or derived from the account email.

Automated checks run in `.github/workflows/security.yml` (Bandit, pip-audit, npm audit, and the backend and frontend test suites).

## Run the frontend

In another terminal:

```powershell
cd frontend
npm ci
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
npm test -- --run
```

Domain terms and grade concepts are documented in [GLOSSARY.md](./GLOSSARY.md).
