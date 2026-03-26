#!/bin/bash

# --- PharmaGPT Start-All Stabilizer ---
# This script ensures services are started in the correct order,
# cleans up stale processes, and optimizes RAM usage by disabling
# non-essential monitoring (Loki/Grafana/Prometheus).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "[1/6] Cleaning up stale processes..."
pkill -f "src.api.server" 2>/dev/null
pkill -f "vite" 2>/dev/null
pkill -f "cloudflared" 2>/dev/null
sleep 2

echo "[2/6] Starting Core Monitoring (Postgres, Clickhouse, Langfuse)..."
# We only start the essentials to save RAM (~700MB saved vs full stack)
docker compose -f "$ROOT_DIR/docker-compose.monitoring.yml" up -d clickhouse db redis langfuse-server langfuse-worker

echo "[3/6] Starting Backend (FastAPI on Port 5005)..."
cd "$ROOT_DIR"
nohup python3 -m src.api.server > "$LOG_DIR/server_out.log" 2>&1 &
echo "$!" > "$ROOT_DIR/backend_pid.txt"

echo "[4/6] Starting Frontend (Vite on Port 3000)..."
cd "$ROOT_DIR/frontend"
nohup npm run dev -- --host 0.0.0.0 --port 3000 > "$LOG_DIR/frontend_out.log" 2>&1 &
echo "$!" > "$ROOT_DIR/frontend_pid.txt"

echo "[5/6] Starting Cloudflare Tunnel (dev.pharmagpt.co)..."
cd "$ROOT_DIR"
nohup cloudflared --config ingress.yml tunnel run > "$LOG_DIR/cloudflared_out.log" 2>&1 &
echo "$!" > "$ROOT_DIR/cloudflared_pid.txt"

echo "[6/6] Finalizing Startup..."
sleep 5
echo "----------------------------------------"
echo "All services started!"
echo "Backend:  http://localhost:5005"
echo "Frontend: http://localhost:3000"
echo "Langfuse: http://localhost:3002"
echo "Tunnel:   https://dev.pharmagpt.co"
echo "----------------------------------------"
echo "To monitor logs, use: tail -f logs/server_out.log"
echo "To stop everything, use: pkill -f src.api.server; pkill -f vite; pkill -f cloudflared; docker compose -f docker-compose.monitoring.yml stop"
