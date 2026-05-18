# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# OS deps for Playwright + Pillow + matplotlib + curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    fonts-liberation fonts-dejavu-core \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libjpeg62-turbo zlib1g libpng16-16 libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv==0.4.20

WORKDIR /app

# Copy lock + manifest first for cache efficiency
COPY pyproject.toml uv.lock ./

# Install dependencies into /opt/venv (no project itself yet)
RUN uv sync --frozen --no-dev --no-install-project --prerelease=allow

# Install Chromium (headless) and OS deps via Playwright
RUN uv run playwright install --with-deps chromium

# Copy source and install project
COPY src ./src
COPY templates ./templates
COPY assets ./assets
COPY config.yaml ./config.yaml
COPY scripts ./scripts

RUN uv sync --frozen --no-dev --prerelease=allow

# Non-root user
RUN useradd --create-home --uid 1000 igqt \
    && mkdir -p /app/data \
    && chown -R igqt:igqt /app /opt/venv

USER igqt

VOLUME ["/app/data"]
EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -fs http://localhost:8080/health || exit 1

CMD ["python", "-m", "ig_qt", "run"]
