#!/bin/bash
# Start Vite frontend and keep it alive
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$ROOT_DIR/frontend"

# Kill any existing vite processes
pkill -f "vite" 2>/dev/null
sleep 1

# Start Vite
cd "$FRONTEND_DIR"
exec npm run dev
