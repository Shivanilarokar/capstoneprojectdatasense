# SupplyChainNexus Product Workspace

SupplyChainNexus is now being consolidated into a product-style monorepo with:

- `backend/`: FastAPI application plus the preserved route engines
- `frontend/`: Vite + React + TypeScript SPA
- `main.py`: top-level launcher surface for the product runtime
- `docker-compose.yml`: local stack for frontend, backend, Postgres, and Neo4j

## Full Stack

Run the full stack locally:

```powershell
cd E:\DatasenseProject\CapstoneprojectDatasense
docker compose up --build
```

If Docker Desktop is not running, start it first. The compose file is at the repo root:

- [docker-compose.yml](./docker-compose.yml)

## Backend Runtime

Run the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8002
```

Current product routers:

- `/health`
- `/auth/*`
- `/google/*`
- `/query/*`
- `/admin/*`
- `/tenants/*`

FastAPI docs:

- `http://127.0.0.1:8002/docs`
- `http://127.0.0.1:8002/openapi.json`

Test the public health endpoint:

```powershell
Invoke-WebRequest http://127.0.0.1:8002/health -UseBasicParsing | Select-Object -ExpandProperty Content
```

Test an authenticated endpoint with a signed app JWT after Google sign-in:

```powershell
$headers = @{ Authorization = "Bearer <PASTE_ACCESS_TOKEN>" }
Invoke-WebRequest http://127.0.0.1:8002/query/ask -Method Post -Headers $headers -ContentType "application/json" -Body '{"question":"Which states had the highest storm damage?"}' | Select-Object -ExpandProperty Content
```

Current auth notes:

- The backend uses bearer auth through `HTTPBearer`.
- Google OAuth login starts at `/google/login`.
- After Google callback, the backend issues a signed application JWT.
- Protected API routes accept only signed application JWTs with the configured issuer and audience.
- `/auth/me` is the simplest endpoint to verify that a token is valid.
- Admin access is driven by the `roles` claim in the signed application JWT.

## LangSmith Setup

Enable tracing by adding these to `.env`:

```powershell
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=supplychainnexus-dev
```

LangChain and LangGraph will pick these up automatically when the backend starts.

## Frontend Runtime

Run the SPA:

```powershell
npm --prefix frontend run dev
```

Build the SPA:

```powershell
npm --prefix frontend run build
```

The frontend is served at:

- `http://127.0.0.1:5173`

If you want the exact command again:

```powershell
cd E:\DatasenseProject\CapstoneprojectDatasense\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## Configuration

Core backend settings are loaded from `.env` through `backend/config.py`.

Key areas:

- OpenAI runtime
- Postgres and Neo4j connectivity
- Google OAuth settings
- application JWT settings
- control-plane and tenant admin settings
- PageIndex and observability paths

Frontend settings are provided through `VITE_*` environment variables for:

- API base URL only

The current frontend uses `VITE_API_BASE_URL` when present and falls back to `http://127.0.0.1:8000`.
The current frontend uses `VITE_API_BASE_URL` when present and falls back to `http://127.0.0.1:8002`.

## Product Direction

The active product surface is:

- orchestrator-backed query workspace
- read-only admin dashboard
- tenant overview
- health check
- external-user auth with Google OAuth and signed application JWTs
- tenant-aware backend runtime resolution
