# Production image: the React UI is built in stage 1 and served by FastAPI in stage 2,
# so the whole app is one container on one port. The database is separate (any
# PostgreSQL 16: Docker, Neon, Supabase, Render, Cloud SQL ...).
#
#   docker build -t smartcart .
#   docker run -p 8000:8000 --env-file .env -e DATABASE_URL=... smartcart
#
# ---- stage 1: web UI ----
FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- stage 2: API + agent ----
FROM python:3.10-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt
COPY smartcart/ smartcart/
COPY db/ db/
COPY docs/evaluation/results.json docs/evaluation/results.json
COPY --from=ui /ui/dist frontend/dist
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health')"
# cloud platforms pass the port in $PORT
CMD ["sh", "-c", "uvicorn smartcart.api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
