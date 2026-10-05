# Imagen única del portal ALEJANDRÍA: FastAPI sirve la API y el build de React.
# Contexto de build: la RAÍZ del repo (necesita uv.lock, portal/backend, portal/frontend y
# portal/config). Ejemplo: docker build -f portal/Dockerfile .

# ---------- Etapa 1: build del frontend ----------
FROM node:26-alpine AS frontend
WORKDIR /build
RUN corepack enable
COPY portal/frontend/package.json portal/frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY portal/frontend/ ./
# Solo el build de Vite: typecheck, lint y tests ya corren en pr_checks.
RUN pnpm exec vite build

# ---------- Etapa 2: backend + estáticos ----------
FROM python:3.12-slim

# Sin .pyc, logs sin buffer (legibles en Cloud Logging) y rutas que lee alejandria.settings.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    CONFIG_DIR=/app/config \
    FRONTEND_DIST=/app/frontend_dist

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

# Dependencias exactas del uv.lock, solo las del backend (sin las de desarrollo ni scripts).
COPY pyproject.toml uv.lock ./
COPY portal/backend/ ./portal/backend/
RUN uv export --frozen --no-dev --package alejandria-backend --no-emit-workspace \
        --no-hashes -o /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt \
    && uv pip install --system --no-cache --no-deps ./portal/backend \
    && rm -rf /tmp/requirements.txt ./portal pyproject.toml uv.lock

COPY portal/config/ /app/config/
COPY --from=frontend /build/dist/ /app/frontend_dist/

# Usuario sin privilegios.
RUN useradd --system --uid 10001 alejandria
USER alejandria

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn alejandria.app:create_app_from_env --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
