# --- Stage 1: Build frontend (Vue) ---
FROM node:20-alpine AS ui-build
WORKDIR /build

# Install dependencies first to leverage Docker layer cache
COPY hajimiUI/package*.json ./hajimiUI/
# If package-lock.json is absent, fall back to npm install
RUN set -eux; \
    cd hajimiUI; \
    (npm ci --no-audit --no-fund || npm install --no-audit --no-fund)

# Copy sources required for the UI build (the build writes into ../app/templates)
COPY hajimiUI ./hajimiUI
COPY app ./app

# Build the UI assets into app/templates
RUN set -eux; cd hajimiUI; npm run build:app


# --- Stage 2: Runtime image ---
FROM python:3.12-slim
WORKDIR /app

# Copy source code
COPY . .
# Overwrite app/templates with freshly built assets from the UI stage
COPY --from=ui-build /build/app/templates ./app/templates

# Install dependencies via uv for speed and smaller image
RUN pip install uv \
 && uv pip install --system --no-cache-dir -r requirements.txt

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
