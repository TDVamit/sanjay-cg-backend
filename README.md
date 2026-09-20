# Sanjay Career Guidance — backend

Sanjay’s backend is a FastAPI service that authenticates users, stores career content in MongoDB, and connects the frontend to AI chat, resume ATS analysis, PDF processing, and career-roadmap APIs.

The browser client is maintained in [TDVamit/Sanjay-CG](https://github.com/TDVamit/Sanjay-CG).

## Capabilities

- User registration, login, refresh, logout, current-user, profile-picture, and protected profile/dashboard/settings endpoints.
- JWT access and refresh tokens with bcrypt password hashing.
- AI chat used by the career assistant and frontend assessment flow to select four roadmap records from the available catalog.
- Resume PDF upload, PDF-to-image conversion through Poppler/pdf2image, and OpenAI-powered ATS category scoring with comments.
- Authenticated CRUD APIs for roadmaps, categories, and guidance agents, with pagination, search, and category filters.
- Health, database-status, Swagger UI, and ReDoc endpoints for local operations and integration checks.

## API surface

The API is mounted under `/api/v1`:

| Area | Representative endpoints |
| --- | --- |
| Authentication | `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me` |
| Protected user APIs | `/protected/profile`, `/protected/dashboard`, `/protected/settings` |
| AI and documents | `/documents/chat`, `/documents/chat-basic`, `/documents/analyze-resume`, `/documents/pdf-to-images` |
| Roadmaps | `/roadmaps/` and `/roadmaps/{roadmap_id}` |
| Categories | `/categories/` and `/categories/{category_id}` |
| Guidance agents | `/guidance-agents/` and `/guidance-agents/{agent_id}` |

Operational endpoints are available at `/`, `/health`, and `/db-status`. FastAPI exposes interactive documentation at `/docs` and `/redoc`.

## Architecture

```text
React/Vite frontend
       │ HTTPS + Authorization: Bearer <access token>
       ▼
FastAPI app (app/main.py)
  ├─ auth + JWT security
  ├─ document router → temporary PDF files → Poppler/pdf2image → OpenAI
  ├─ roadmap/category/guidance-agent routers
  └─ MongoDB connection via Motor
```

The API owns authentication, validation, persistence, temporary document processing, and calls to OpenAI. The frontend owns navigation, assessment form state, token storage/refresh, and presentation. In the assessment flow, the frontend supplies answers and the roadmap catalog to `/documents/chat`; the model returns four exact roadmap IDs, which the frontend validates before displaying them.

## Tech stack

- Python 3.12+, FastAPI, Uvicorn, Pydantic Settings
- Motor/PyMongo for asynchronous MongoDB access
- `python-jose` and Passlib/bcrypt for JWT and password security
- OpenAI Python client for chat and image-based resume analysis
- `pdf2image`, Poppler, Pillow, and `python-multipart` for uploads and PDF conversion
- `uv.lock` and `requirements.txt` for dependency management

## Safe local setup

Requirements: Python 3.12+, MongoDB, and Poppler. On macOS, install Poppler with `brew install poppler`; on Debian/Ubuntu, install `poppler-utils` with the system package manager.

```bash
git clone https://github.com/TDVamit/sanjay-cg-backend.git
cd sanjay-cg-backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a local `.env` file. Use your own values; never commit this file or paste real secrets into documentation:

```env
MONGODB_URL=mongodb://127.0.0.1:27017
DATABASE_NAME=sanjay_cg
JWT_SECRET_KEY=replace-with-a-long-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
SERVER_HOST=127.0.0.1
SERVER_PORT=8000
CORS_ORIGINS=["http://localhost:5173"]
OPENAI_API_KEY=replace-with-your-openai-key
OPENAI_MODEL=gpt-4.1
```

The settings loader is case-insensitive, so these names are suitable even though the code’s model fields are lowercase. `MONGODB_URL` is required. `OPENAI_API_KEY` is required for AI features; without it, document AI routes report the AI service as unavailable. The frontend should point `VITE_BACKEND_SERVER_URL` at `http://127.0.0.1:8000/api/v1`.

## Run the service

For the repository’s development launcher:

```bash
python start.py
```

`start.py` checks for Poppler, installs Python requirements with `uv` when available, and starts Uvicorn with reload enabled. For a more predictable environment, install dependencies yourself and run Uvicorn directly:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the OpenAPI UI.

## Configuration reference

| Variable | Required | Purpose |
| --- | --- | --- |
| `MONGODB_URL` | Yes | MongoDB connection string |
| `DATABASE_NAME` | No | Database name; defaults to `fastapi_auth_db` |
| `JWT_SECRET_KEY` | No in code, required for safe production | JWT signing secret; replace the development default |
| `JWT_ALGORITHM` | No | JWT algorithm; defaults to `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Access-token lifetime; defaults to `30` |
| `SERVER_HOST` / `SERVER_PORT` | No | Bind address and port; defaults to `127.0.0.1:8000` |
| `CORS_ORIGINS` | Defined in settings | Intended allowed-origin list |
| `OPENAI_API_KEY` | For AI features | OpenAI credential, server-side only |
| `OPENAI_MODEL` | No | OpenAI model; defaults to `gpt-4.1` |

## Production notes

- Run behind an HTTPS reverse proxy or managed platform and use a production Uvicorn process configuration.
- Generate a strong unique `JWT_SECRET_KEY`; do not use the placeholder default.
- Restrict CORS to the deployed frontend origin. Current `app/main.py` still uses `allow_origins=["*"]`, so CORS hardening remains an application task.
- Keep MongoDB and OpenAI credentials in the host’s secret manager/environment, not in Git, README examples, browser variables, or logs.
- The current checkout includes a tracked `.env` and a manual database smoke script; rotate any credentials they may contain and remove sensitive artifacts from repository history before treating the project as production-ready.
- Add request-size/rate limits and structured error logging before exposing PDF and AI endpoints publicly.
- No verified public API deployment URL is present in the repository; `/docs` is therefore documented for local use only.

## Development status

This is an active prototype backend supporting the Sanjay frontend. The repository contains a manual database connectivity script (`test.py`), but no automated pytest suite or CI test workflow was found. Validate changes with the OpenAPI docs and a local MongoDB/OpenAI-enabled integration run.

## Project layout

```text
app/
  main.py                 FastAPI app, middleware, routers, health endpoints
  core/                   settings, JWT security, OpenAI agent, PDF utilities
  database/               Motor/MongoDB connection lifecycle
  models/                 Pydantic request and response models
  routers/                auth, documents, roadmaps, categories, guidance agents
requirements.txt          pinned runtime dependencies
pyproject.toml            project metadata and uv configuration
start.py                  development startup helper
```

## Links

- [Backend repository](https://github.com/TDVamit/sanjay-cg-backend)
- [Frontend repository](https://github.com/TDVamit/Sanjay-CG)
