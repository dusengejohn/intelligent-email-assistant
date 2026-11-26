# The whole Email Generator in one image (story 3b.3): a multi-stage build.

# --- Stage 1: build the page with Node. Only its output (web/dist) is kept.
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web ./
# Build-time setting written into the page: where "Open the inbox" points
ARG VITE_INBOX_URL=http://localhost:8080
ENV VITE_INBOX_URL=$VITE_INBOX_URL
RUN npm run build

# --- Stage 2: the API (Python + uv), which also serves the built page
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies first (cached unless pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
# The page: app/main.py serves /app/static at "/" (Node itself never reaches this image)
COPY --from=web /web/dist ./static

# Run as an unprivileged user, like the backend (UID/GID 1000). The generator
# writes no files, so everything stays owned by root (read-only for the app).
ARG UID=1000
ARG GID=1000
RUN groupadd --gid "$GID" app \
    && useradd --uid "$UID" --gid app --no-create-home --shell /usr/sbin/nologin app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
