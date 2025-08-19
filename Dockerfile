# Strava Sensor Webhook Listener
# Environment variables documented in README.md

# renovate: datasource=github-releases depName=astral-sh/uv
ARG UV_VERSION=0.8.11

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# Build dependencies and install packages
FROM python:3.13-slim AS builder

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

# Copy project files for dependency resolution
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install production dependencies only
RUN uv sync --frozen --no-dev

# Final runtime image
FROM python:3.13-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app

# Copy entire application from builder
COPY --from=builder /app /app

RUN chown -R appuser:appuser /app
USER appuser

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["strava-webhook-listener"]
