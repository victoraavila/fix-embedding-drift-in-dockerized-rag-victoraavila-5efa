#!/usr/bin/env bash
set -euo pipefail

cd /root/task || exit 0

echo "[kill.sh] Stopping and removing Docker Compose services..."
if command -v docker-compose >/dev/null 2>&1; then
  docker-compose down --volumes --remove-orphans || true
else
  docker compose down --volumes --remove-orphans || true
fi

echo "[kill.sh] Removing project-related Docker images (if any)..."
IMAGES=$(docker images -q '*task*' 2>/dev/null || true)
if [ -n "$IMAGES" ]; then
  docker rmi $IMAGES 2>/dev/null || true
fi

echo "[kill.sh] Removing chroma_data volume (if present)..."
VOLUME=$(docker volume ls -q | grep 'chroma_data' || true)
if [ -n "$VOLUME" ]; then
  docker volume rm $VOLUME 2>/dev/null || true
fi

echo "[kill.sh] Removing task directory /root/task ..."
rm -rf /root/task || true

echo "[kill.sh] Cleanup complete."
