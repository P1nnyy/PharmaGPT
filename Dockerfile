# Base Image (Lightweight Python)
FROM python:3.11-slim-bookworm

# Set Working Directory
WORKDIR /app

# Install System Dependencies (Crucial for OpenCV Headless)
# libgl1: Required for cv2
# libglib2.0-0: Required for some cv2 utility functions
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy Requirements first for Caching
COPY requirements.txt .

# Install Python Dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Force install missing deps
RUN pip install langgraph chromadb langchain tiktoken

# Copy Codebase
COPY src/ ./src/
COPY data/ ./data/
# Note: config is assumed to be in src or root? 
# Project structure shows 'config' in root.
COPY config/ ./config/

# Environment Variables (Default)
ENV PYTHONUNBUFFERED=1

# Expose Port
EXPOSE 8000

# Run Command
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
