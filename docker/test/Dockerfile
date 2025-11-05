# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Basic tools and build deps for common Python wheels fallbacks
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl ca-certificates build-essential pkg-config git \
		build-essentials \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Rust-based Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /workspace

# Default command is set via docker-compose.test.yml
