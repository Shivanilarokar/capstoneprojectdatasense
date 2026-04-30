# Azure App Service Deployment

This repository is ready to deploy as two separate Azure Web Apps:

- `backend`: FastAPI API on Azure App Service for Linux
- `frontend`: Vite/React SPA on a separate Azure Web App for Linux

## Target architecture

Use these Azure resources for production:

- `Resource Group`: one product resource group per environment
- `App Service Plan`: Linux, at least `P1v3` for production
- `Backend Web App`: Python 3.11
- `Frontend Web App`: Node 20 LTS
- `Azure Database for PostgreSQL Flexible Server`: shared for sanctions data, NL-SQL data, and control-plane RBAC
- `Neo4j AuraDB` or managed Neo4j endpoint: GraphRAG store
- `Azure Key Vault`: secrets
- `Application Insights` plus Log Analytics: logs and telemetry
- `Google OAuth client`: authentication

## Why this split matches the codebase

- The backend is FastAPI in [backend/main.py](../backend/main.py).
- The frontend is a browser SPA using React Router in [frontend/src/routes/router.tsx](../frontend/src/routes/router.tsx).
- The frontend calls the backend through `VITE_API_BASE_URL` in [frontend/src/lib/apiBase.ts](../frontend/src/lib/apiBase.ts).
- Google login starts on the backend at `/google/login` and returns to the frontend callback route `/auth/callback`.
- RBAC must not use local SQLite in production. The code already supports `CONTROL_PLANE_DATABASE_URL` in [backend/app/control_plane/db.py](../backend/app/control_plane/db.py).

## Required production changes in Azure configuration

### 1. Backend Web App

Create a Linux Web App with:

- Runtime stack: `PYTHON|3.11`
- Startup command: `backend/startup.sh`
- Always On: `On`
- HTTPS only: `On`
- Minimum TLS version: `1.2`

Backend app settings:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `PAGEINDEX_API_KEY`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`
- `GRAPH_TENANT_ID`
- `PGHOST`
- `PGUSER`
- `PGPORT`
- `PGDATABASE`
- `PGPASSWORD`
- `PGSSLMODE=require`
- `PGCONNECT_TIMEOUT=15`
- `CONTROL_PLANE_DATABASE_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI=https://<backend-app>.azurewebsites.net/google/callback`
- `GOOGLE_FRONTEND_REDIRECT_URI=https://<frontend-app>.azurewebsites.net/auth/callback`
- `GOOGLE_SCOPE=openid email profile`
- `APP_AUTH_SECRET`
- `APP_AUTH_AUDIENCE=supplychainnexus-api`
- `APP_AUTH_ISSUER=supplychainnexus-google-sso`
- `GOOGLE_DEFAULT_TENANT_KEY=default`
- `CORS_ALLOWED_ORIGINS=https://<frontend-app>.azurewebsites.net`
- `PAGEINDEX_SECTIONS_JSON=/home/site/data/ingestion/sec/extracted_10k_sections.json`
- `PAGEINDEX_DOCS_DIR=/home/site/data/pageindex/docs`
- `PAGEINDEX_WORKSPACE_DIR=/home/site/data/pageindex/workspace`
- `PAGEINDEX_OUTPUT_DIR=/home/site/data/pageindex/output`
- `OBSERVABILITY_DIR=/home/site/data/observability`
- `ALERT_EVENT_LOG=/home/site/data/observability/alerts.jsonl`
- Optional LangSmith settings if used

Recommended additional backend settings:

- `WEB_CONCURRENCY=2`
- `GUNICORN_TIMEOUT=180`

### 2. Frontend Web App

Create a Linux Web App with:

- Runtime stack: `NODE|20-lts`
- Startup command: `node server.cjs`
- Always On: `On`
- HTTPS only: `On`
- Minimum TLS version: `1.2`

The frontend artifact is prebuilt in GitHub Actions. It serves the `dist/` folder with SPA fallback through [frontend/server.cjs](../frontend/server.cjs).

Frontend app settings are optional because `VITE_API_BASE_URL` is injected at build time from GitHub Actions using the repository variable `AZURE_BACKEND_BASE_URL`.

## Database and state requirements

### Control plane RBAC

Do not use the default local SQLite fallback in production.

Set:

- `CONTROL_PLANE_DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>?sslmode=require`

Create a dedicated control-plane database or schema for:

- `tenants`
- `users`
- `user_tenant_memberships`
- `user_role_assignments`

Recommended first production setup:

- keep one PostgreSQL Flexible Server per environment
- create a separate database named `scn_control_plane`
- create a dedicated login such as `scn_control_plane_app`
- point `CONTROL_PLANE_DATABASE_URL` to that database

After the database is reachable from the backend host, initialize it with:

```powershell
.\.venv\Scripts\python.exe -m backend.app.control_plane.bootstrap `
  --database-url "postgresql://scn_control_plane_app:<PASSWORD>@<HOST>:5432/scn_control_plane?sslmode=require" `
  --seed-admin-email "you@example.com" `
  --seed-admin-name "Workspace Admin" `
  --tenant-key "default" `
  --role admin
```

The bootstrap command:

- creates the control-plane tables if they do not exist
- optionally seeds the first admin assignment
- returns a JSON summary

### Sanctions and NL-SQL PostgreSQL

The sanctions route and NL-SQL flows use PostgreSQL directly through [backend/nlsql/db.py](../backend/nlsql/db.py). For production:

- Prefer Azure PostgreSQL Flexible Server with private networking
- Allow backend outbound access on TCP `5432`
- Keep TLS enforced with `PGSSLMODE=require`

### Neo4j

Set the managed Neo4j endpoint in:

- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`

### Filesystem-backed runtime paths

This codebase writes runtime artifacts for:

- PageIndex workspace/output
- LangGraph checkpoints and traces
- alert logs

Use `/home/site/data/...` on App Service for the first production cut. It is better than deploying into `wwwroot`.

If you expect scale-out or high write volume, move these artifacts to Blob Storage and centralized logging later.

## Google OAuth production setup

In Google Cloud Console, set authorized redirect URIs to:

- `https://<backend-app>.azurewebsites.net/google/callback`

The frontend callback is not a Google redirect URI. It is the application redirect target used after your backend finishes token exchange:

- `https://<frontend-app>.azurewebsites.net/auth/callback`

## GitHub Actions CI/CD

This repository now includes:

- [.github/workflows/deploy-backend.yml](../.github/workflows/deploy-backend.yml)
- [.github/workflows/deploy-frontend.yml](../.github/workflows/deploy-frontend.yml)

Both workflows use Azure OIDC through `azure/login@v2`.

### GitHub secrets

Create these repository or environment secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

### GitHub repository variables

Create these repository or environment variables:

- `AZURE_RESOURCE_GROUP`
- `AZURE_BACKEND_WEBAPP_NAME`
- `AZURE_FRONTEND_WEBAPP_NAME`
- `AZURE_BACKEND_BASE_URL`

Example:

- `AZURE_BACKEND_WEBAPP_NAME=scn-api-prod`
- `AZURE_FRONTEND_WEBAPP_NAME=scn-web-prod`
- `AZURE_BACKEND_BASE_URL=https://scn-api-prod.azurewebsites.net`

## PageIndex data bootstrap

The PageIndex route needs the extracted SEC sections JSON available at runtime.

You now have two supported choices:

1. Deploy `data/ingestion/sec/extracted_10k_sections.json` with the backend artifact.
2. Upload the file to the backend persistent storage path and set:
   - `PAGEINDEX_SECTIONS_JSON=/home/site/data/ingestion/sec/extracted_10k_sections.json`

The current backend workflow includes the local `extracted_10k_sections.json` file when it exists in the repository.

## Azure setup order

1. Create the Azure PostgreSQL Flexible Server.
2. Create or connect the Neo4j production instance.
3. Create the App Service Plan.
4. Create the backend Web App.
5. Create the frontend Web App.
6. Configure backend app settings.
7. Configure backend startup command to `backend/startup.sh`.
8. Configure frontend startup command to `node server.cjs`.
9. Add Google OAuth redirect URIs.
10. Add GitHub OIDC federated credential to the Azure identity used by Actions.
11. Set GitHub secrets and variables.
12. Push to `main` or run the workflows manually.

## First deployment checklist

After deployment:

1. Open `https://<backend-app>.azurewebsites.net/health`
2. Open `https://<frontend-app>.azurewebsites.net/`
3. Start Google sign-in from `/signin`
4. Confirm `/auth/callback` resolves on the frontend Web App
5. Verify `/auth/me` with the issued token
6. Verify `/admin` loads for an `admin`
7. Run a query that exercises:
   - PostgreSQL
   - Neo4j
   - OpenAI
   - PageIndex

## What is not production-ready until configured

- Leaving RBAC on local SQLite
- Leaving PostgreSQL on public access without proper allowlists or private networking
- Leaving secrets in `.env` instead of Azure configuration
- Running without custom domains and HTTPS certificate management
- Relying only on App Service local files for long-term audit retention
