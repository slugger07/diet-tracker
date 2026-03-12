FROM python:3.11-slim

# System deps for SQLite and general build requirements
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        sqlite3 \
        libsqlite3-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a directory for the SQLite database so it can be mounted as a volume
RUN mkdir -p /app/data

# Default env: point SQLite DB to the data directory
ENV DATABASE_URL="sqlite:///data/nutrilog.db"

# Expose Streamlit (8501) and FastAPI (8000) ports
EXPOSE 8501 8000

# Healthcheck against Streamlit
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Start both Streamlit and the FastAPI server
CMD ["sh", "-c", "uvicorn api.routes:app --host 0.0.0.0 --port 8000 & streamlit run app.py --server.port 8501 --server.address 0.0.0.0"]
