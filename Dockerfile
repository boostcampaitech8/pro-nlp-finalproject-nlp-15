# --- 1. Base Image ---
# Use Python 3.13 slim - extremely lightweight
FROM python:3.13-slim

# --- 2. Environment Setup ---
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8501

WORKDIR /app

# --- 3. Install uv ---
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# --- 4. Install Core Dependencies ---
# We ONLY install the core dependencies. 
# Optional extras (local, preprocess, scraper) are EXCLUDED to keep the image minimal.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# --- 5. Copy Application Source ---
# .dockerignore will handle excluding large/unnecessary files
COPY . .

# --- 6. Execution ---
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run the application
ENTRYPOINT ["uv", "run", "streamlit", "run", "app/chatbot_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
