FROM python:3.12-slim

# Bring in the uv binary from its official image
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first (cached unless pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

# Run as an unprivileged user (least privilege). UID/GID 1000 match the default
# WSL/Linux user, so files written to the ./data bind mount are owned by you, not
# root. Override if needed: docker compose build --build-arg UID=$(id -u)
ARG UID=1000
ARG GID=1000
RUN groupadd --gid "$GID" app \
    && useradd --uid "$UID" --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data \
    && chown app:app /app/data
# Code and .venv stay owned by root: the app can read and run them, not change them
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
