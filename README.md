# NutriLog India 🥗

A diet tracking app combining **Streamlit** UI + **FastAPI** backend with local LLM support via **Ollama** and **SQLite** for nutrition analysis.

---

## 🚀 Quick Start with Docker

### Prerequisites
- Docker & Docker Compose installed

### Run Everything in One Command

```bash
git clone <your-repo-url>
cd diet-tracker-main

docker compose up --build -d
```

Then open:
- **Streamlit UI**: http://localhost:8501
- **FastAPI Docs**: http://localhost:8000/docs

### First Time Setup
Pull the LLM model (one-time):
```bash
docker compose exec ollama ollama pull llama3.1
```

Check that the model loaded:
```bash
docker compose exec ollama ollama list
```

---

## 🛑 Stop the Stack

```bash
docker compose down
```

---

## 📦 Configuration

All settings are in [.env](.env):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | LLM backend (ollama/groq) |
| `OLLAMA_MODEL` | `llama3.1` | Model to use |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama endpoint |
| `DATABASE_URL` | `sqlite:///data/nutrilog.db` | DB path |
| `SEARCH_PROVIDER` | `duckduckgo` | Web search |

### Switch to Groq (Cloud LLM)
Edit [.env](.env):
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your-key-here
GROQ_MODEL=llama-3.1-8b-instant
```

---

## 🐳 Using Pre-built Docker Images

### Option 1: Docker Hub
```bash
docker pull <username>/nutrilog-india:latest
docker run -p 8501:8501 -p 8000:8000 \
  -v nutrilog-data:/app/data \
  --env-file .env \
  <username>/nutrilog-india:latest
```

### Option 2: GitHub Container Registry
```bash
docker pull ghcr.io/<username>/nutrilog-india:latest
docker run -p 8501:8501 -p 8000:8000 \
  -v nutrilog-data:/app/data \
  --env-file .env \
  ghcr.io/<username>/nutrilog-india:latest
```

---

## 🏗️ Local Development (Without Docker)

### Setup Python Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Start Ollama Locally
```bash
ollama serve
# in another terminal
ollama pull llama3.1
```

### Configure .env for Local Dev
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
DATABASE_URL=sqlite:///nutrilog.db
```

### Run Streamlit
```bash
streamlit run app.py
```

### Run FastAPI (optional, separate terminal)
```bash
uvicorn api.routes:app --host 0.0.0.0 --port 8000
```

---

## 📤 Publishing Your Docker Image

### Push to Docker Hub

1. **Create Docker Hub account** (free): https://hub.docker.com/signup

2. **Build & Tag**:
   ```bash
   docker build -t <username>/nutrilog-india:latest .
   docker tag <username>/nutrilog-india:latest <username>/nutrilog-india:v1.0
   ```

3. **Login**:
   ```bash
   docker login
   ```

4. **Push**:
   ```bash
   docker push <username>/nutrilog-india:latest
   docker push <username>/nutrilog-india:v1.0
   ```

5. **Share**: Others can now run:
   ```bash
   docker pull <username>/nutrilog-india:latest
   docker compose up -d
   ```

### Push to GitHub Container Registry (Recommended)

1. **Create Personal Access Token** (PAT):
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select `write:packages` and `read:packages`
   - Copy the token

2. **Login to GHCR**:
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u <username> --password-stdin
   ```

3. **Build & Tag**:
   ```bash
   docker build -t ghcr.io/<username>/nutrilog-india:latest .
   docker tag ghcr.io/<username>/nutrilog-india:latest ghcr.io/<username>/nutrilog-india:v1.0
   ```

4. **Push**:
   ```bash
   docker push ghcr.io/<username>/nutrilog-india:latest
   docker push ghcr.io/<username>/nutrilog-india:v1.0
   ```

5. **Share**: Others use:
   ```bash
   docker pull ghcr.io/<username>/nutrilog-india:latest
   ```

---

## 🔄 CI/CD: Automate Image Builds

To auto-build and push on every commit, add [.github/workflows/docker-publish.yml](.github/workflows/docker-publish.yml):

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main, master]
    tags: ['v*']
  pull_request:
    branches: [main, master]

jobs:
  push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      
      - uses: docker/setup-buildx-action@v3
      
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:latest
            ghcr.io/${{ github.repository }}:${{ github.sha }}
```

---

## 📋 Project Structure

```
.
├── app.py                 # Streamlit UI
├── api/routes.py         # FastAPI endpoints
├── core/                  # LLM, nutrition, search
├── db/                    # Database models & queries
├── ui/                    # Charts & components
├── Dockerfile            # Container image
├── docker-compose.yml    # Multi-container stack
├── requirements.txt      # Python dependencies
└── .env                  # Configuration
```

---

## ✅ Features

- ✨ **Food Logging**: Enter meals and get instant nutrition breakdown
- 🤖 **AI Parsing**: Ollama LLM parses free-form text into structured nutrients
- 📊 **Analytics**: Weekly charts, macro breakdown, frequent foods
- 💾 **SQLite**: Lightweight, embedded database
- 🐳 **Docker Ready**: One-command deployment
- 🔄 **Extensible**: Swap Ollama for Groq or add PostgreSQL

---

## 🐛 Troubleshooting

### Container won't start
```bash
docker compose logs nutrilog
```

### Ollama model not found
```bash
docker compose exec ollama ollama list
docker compose exec ollama ollama pull llama3.1
```

### Database errors
```bash
# Reset DB (caution: deletes data)
docker compose exec nutrilog rm /app/data/nutrilog.db
docker compose restart nutrilog
```

### Port already in use
```bash
# Change ports in docker-compose.yml or:
docker compose down
lsof -i :8501
```

---

## 📝 License

[Add your license here]

---

## 🤝 Contributing

Pull requests welcome! Please ensure Docker builds successfully:
```bash
docker build -t nutrilog-india .
```

