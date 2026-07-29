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

Server runs at `http://localhost:8080`. Dashboard at `http://localhost:8080/ui/index.html`.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2:1b` | Model to use for AI queries |
| `DATABASE_URL` | — | PostgreSQL connection URL |

## Railway Deployment

The project includes a `Dockerfile` and `railway.json` for deployment to Railway.

### How it works

1. The Dockerfile uses a multi-stage build to copy the `ollama` binary into a Python 3.11-slim image
2. Supervisor manages three processes:
   - **ollama** - The Ollama server (listens on port 11434)
   - **model-puller** - Pulls the configured model on startup, signals when ready
   - **api-server** - Waits for the model to be ready, then starts the Python API server
3. The API server connects to Ollama at `http://localhost:11434`

### Deploy

```bash
# Install Railway CLI
# npm i -g @railway/cli

# Login and link project
railway login
railway link

# Deploy
railway up
```

Railway reads `railway.json` for build/deploy configuration. The exposed port is `8080`.

### Customizing the Model

Edit `railway.json` to change the `OLLAMA_MODEL` env var, or set it via Railway dashboard:

| Model | Size | RAM Required |
|---|---|---|
| `llama3.2:1b` | ~800MB | 512MB+ |
| `llama3.2:3b` | ~2GB | 2GB+ |
| `phi:2.7b` | ~1.6GB | 2GB+ |
| `mistral:7b` | ~4.1GB | 8GB+ |

## Running Anytime

```bash
# Ensure Ollama is running
ollama serve &

# Pull model if needed
ollama pull llama3.2:1b

# Start API server
python scripts/api_server.py
```
