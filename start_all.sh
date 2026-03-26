#!/bin/bash

# --- PharmaGPT Start-All Stabilizer ---
# This script ensures services are started in the correct order,
# cleans up stale processes, and optimizes RAM usage.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
# Load environment variables
if [ -f "$ROOT_DIR/.env" ]; then
    echo "Loading environment variables from .env..."
    set -a
    source "$ROOT_DIR/.env"
    set +a
fi

echo "[1/6] Cleaning up stale processes..."
# Kill by pattern (be specific to avoid killing VS Code)
pkill -9 -f "src.api.server" 2>/dev/null
pkill -9 -f "cloudflared" 2>/dev/null
# Note: vite and node are handled by port cleanup below to avoid killing IDE extensions

# Clean up PIDs from files
for f in backend_pid.txt frontend_pid.txt cloudflared_pid.txt; do
    if [ -f "$ROOT_DIR/$f" ]; then
        kill -9 $(cat "$ROOT_DIR/$f") 2>/dev/null
        rm "$ROOT_DIR/$f"
    fi
done

# Force kill anything remaining on key ports (Backend and Frontend only)
# Avoid killing 3001, 3002 as they are managed by Docker Desktop and killing them breaks the bridge.
echo "Ensuring ports 5005, 3000, 5173 are free..."
lsof -ti :3000,5005,5173 | xargs kill -9 2>/dev/null
sleep 2

# Check if Docker is running (Resilient Check)
if docker info >/dev/null 2>&1; then
    SKIP_MONITORING=false
else
    # Try one more time with explicit desktop-linux context if on Mac
    if docker --context desktop-linux info >/dev/null 2>&1; then
        echo "Using desktop-linux context for Docker..."
        export DOCKER_CONTEXT=desktop-linux
        SKIP_MONITORING=false
    else
        echo "WARNING: Docker daemon connection failed. Attempting to start monitoring anyway..."
        SKIP_MONITORING=false # Force attempt because daemon might be alive but CLI config is messy
    fi
fi

if [ "$SKIP_MONITORING" = false ]; then
    echo "[2/6] Starting Core Monitoring (Postgres, Clickhouse, Langfuse)..."
    docker compose -f "$ROOT_DIR/docker-compose.monitoring.yml" up -d clickhouse db redis langfuse-server langfuse-worker
    # Wait for DB to be ready to avoid backend connection errors
    echo "Waiting for core services to initialize..."
    sleep 5
else
    echo "[2/6] Skipping Monitoring (Docker Unavailable)..."
fi

echo "[3/6] Starting Backend (FastAPI on Port 5005)..."
cd "$ROOT_DIR"
# Set environment for GRPC fixes
export GRPC_DNS_RESOLVER=native
nohup python3 -m src.api.server > "$LOG_DIR/server_out.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$ROOT_DIR/backend_pid.txt"

# Wait for backend to be ready
echo "Waiting for Backend to listen on 5005..."
ATTEMPTS=0
while ! lsof -i :5005 >/dev/null 2>&1 && [ $ATTEMPTS -lt 15 ]; do
    sleep 2
    ATTEMPTS=$((ATTEMPTS+1))
    printf "."
done
echo ""

if ! lsof -i :5005 >/dev/null 2>&1; then
    echo "ERROR: Backend failed to start on port 5005. Check $LOG_DIR/server_out.log"
    exit 1
fi

echo "[4/6] Starting Frontend (Vite on Port 3000)..."
cd "$ROOT_DIR/frontend"
nohup npm run dev -- --host 0.0.0.0 --port 3000 > "$LOG_DIR/frontend_out.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$ROOT_DIR/frontend_pid.txt"

echo "[5/6] Starting Cloudflare Tunnel (dev.pharmagpt.co)..."
cd "$ROOT_DIR"
nohup cloudflared --config ingress.yml tunnel run > "$LOG_DIR/cloudflared_out.log" 2>&1 &
TUNNEL_PID=$!
echo "$TUNNEL_PID" > "$ROOT_DIR/cloudflared_pid.txt"

echo "[6/6] Finalizing Startup..."
sleep 3
echo "----------------------------------------"
echo "All services started!"
echo "Backend:  http://localhost:5005 (ALIVE: PID $BACKEND_PID)"
echo "Frontend: http://localhost:3000 (ALIVE: PID $FRONTEND_PID)"
if [ "$SKIP_MONITORING" = false ]; then
    echo "Langfuse: http://localhost:3002"
fi
echo "Tunnel:   https://dev.pharmagpt.co"
echo "----------------------------------------"
echo "To monitor logs, use: tail -f logs/server_out.log"

