# ── Stage 1: Build deps ───────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools (needed for some pip packages)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Don't run as root inside the container
RUN useradd --no-create-home --shell /bin/false botuser
USER botuser

# Healthcheck: verifies the process is still alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD pgrep -f "python main.py" || exit 1

CMD ["python", "main.py"]