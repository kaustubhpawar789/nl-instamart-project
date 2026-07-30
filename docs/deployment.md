# Deployment

## Local Development

### Prerequisites
- Python 3.9+
- Ollama installed (`brew install ollama` on macOS, or `curl -fsSL https://ollama.com/install.sh | sh` on Linux)

### Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start Ollama (in a separate terminal)
ollama serve

# Pull the default model
ollama pull llama3.2:1b

# (Optional) Use a different model
# export OLLAMA_MODEL=mistral
# ollama pull mistral

# Start the API server
python scripts/api_server.py
```

Server runs at `http://localhost:8080`. Dashboard at `http://localhost:8080/ui/index.html`. Shop at `http://localhost:8080/ui/shop.html`.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2:1b` | Model to use for AI queries |
| `DATABASE_URL` | — | PostgreSQL connection URL |

---

## Railway Deployment (Production)

The project is configured for Railway's **Python Nixpacks builder** — no Dockerfile required for production deployment. Every push to the connected GitHub branch triggers an automatic redeploy.

### Step 1: Push Code to GitHub

```bash
# If you haven't already, create a GitHub repository and push:
git remote add origin git@github.com:<your-org>/<your-repo>.git
git push -u origin main
```

### Step 2: Create a Railway Project

1. Go to [railway.app](https://railway.app) and log in (GitHub OAuth).
2. Click **"New Project"** → **"Deploy from GitHub repo"**.
3. Select your repository (e.g., `your-org/nl-instamart-project`).
4. Railway auto-detects `requirements.txt` and `Procfile` → starts building immediately.

### Step 3: Provision PostgreSQL

1. In the same Railway project dashboard, click **"New"** → **"Database"** → **"Add PostgreSQL"**.
2. Wait ~30 seconds for the database to provision.
3. Railway automatically injects the `DATABASE_URL` environment variable into the app service — no manual configuration needed.

### Step 4: Initialize the Database Schema

Railway provides a web terminal for your service. Click the app service → **"Connect"** tab → launch the shell, then run:

```bash
python database/init_db.py
python database/seed_mock_data.py
```

This creates all Phase 1 + Phase 2 tables and seeds them with 60 products, 10 users, recommendations, and feedback data.

### Step 5: Verify Deployment

1. In Railway, click the **"Deployments"** tab to watch the build log.
2. Once deployed, click the **"Generate Domain"** button (or use the auto-generated `*.railway.app` URL).
3. Visit `https://<your-app>.railway.app/ui/index.html` — the dashboard loads.
4. Visit `https://<your-app>.railway.app/ui/shop.html` — the Instamart shop loads.
5. API health check: `https://<your-app>.railway.app/api/kpis` returns JSON.

### GitHub Auto-Deploy

Once connected, every `git push origin main` triggers an automatic redeploy:
1. Railway fetches the latest commit.
2. Nixpacks runs `pip install -r requirements.txt`.
3. The app starts on the port specified by the `PORT` env var (auto-injected by Railway).
4. If the build fails, Railway rolls back to the last successful deployment.

---

## Configuration Files

| File | Purpose |
|---|---|
| `Procfile` | Railway start command: `web: python scripts/api_server.py` |
| `railway.json` | Build/deploy configuration (Nixpacks builder, health check path, restart policy) |
| `requirements.txt` | Python dependencies (auto-detected by Railway) |
| `Dockerfile` | Kept for local/Ollama-full deployments (Railway uses Nixpacks, not this file) |

---

## Railway Environment Variables

| Variable | Source | Required | Description |
|---|---|---|---|
| `PORT` | Railway (auto-injected) | Yes | Port the web process listens on (usually 8080) |
| `DATABASE_URL` | Railway PostgreSQL plugin (auto-injected) | Yes | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | Set manually in Railway dashboard | No | External Ollama server URL (for AI features) |
| `OLLAMA_MODEL` | Set manually in Railway dashboard | No | Model name (e.g., `llama3.2:1b`) |

To set a custom variable: Railway Dashboard → App Service → **Variables** tab → **"New Variable"**.

### Ollama & AI Features on Railway

**The deployed container does NOT include Ollama** (container resource limits make it impractical). AI-powered endpoints (`/api/search`, `/api/recommend`, `/api/per-product-recommend`) will return `503` with `{"error": "Ollama service unavailable"}` unless you configure an external Ollama instance.

To enable AI features in production:
1. Run Ollama on a separate machine (or your local dev machine).
2. Set `OLLAMA_BASE_URL` to the external Ollama IP: `http://<your-ip>:11434`.
3. Set `OLLAMA_MODEL` to your preferred model (e.g., `llama3.2:1b`).

For the final presentation, you can run Ollama locally and configure the env var, or demonstrate the non-AI features (product grid, cart sync, dashboard KPIs, charts, user management, database filtering/sorting).

---

## Railway Dashboard URLs

| Page | Path |
|---|---|
| Discovery Engine Dashboard | `/ui/index.html` |
| Instamart Shop Frontend | `/ui/shop.html` |
| API Health Check | `/api/kpis` |
| Products API | `/api/products` |
| Users API | `/api/users` |

---

## Running Anytime (Local)

```bash
# Ensure Ollama is running
ollama serve &

# Pull model if needed
ollama pull llama3.2:1b

# Start API server
python scripts/api_server.py
```
