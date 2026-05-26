#!/usr/bin/env bash
set -euo pipefail

cd /root/task

if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs || true)
fi

echo "[run.sh] Building and starting Docker services..."
docker-compose up -d --build

# Wait for chroma-init to complete successfully (Exited with code 0)
MAX_WAIT_INIT=60
SLEEP_INTERVAL=5
ELAPSED=0

echo "[run.sh] Waiting for chroma-init service to complete..."
while [ "$ELAPSED" -lt "$MAX_WAIT_INIT" ]; do
  if docker ps --format '{{.Names}}' | grep -q '^chroma-init$'; then
    # still running
    echo "[run.sh] chroma-init is still running..."
  else
    # container exited; check status
    if docker ps -a --format '{{.Names}}' | grep -q '^chroma-init$'; then
      STATUS=$(docker inspect -f '{{.State.Status}}' chroma-init)
      EXIT_CODE=$(docker inspect -f '{{.State.ExitCode}}' chroma-init)
      echo "[run.sh] chroma-init status: $STATUS (exit code $EXIT_CODE)"
      if [ "$STATUS" = "exited" ] && [ "$EXIT_CODE" -eq 0 ]; then
        echo "[run.sh] chroma-init completed successfully."
        break
      else
        echo "[run.sh] chroma-init failed or exited unexpectedly. Check logs with 'docker logs chroma-init'."
        exit 1
      fi
    fi
  fi
  sleep "$SLEEP_INTERVAL"
  ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

if [ "$ELAPSED" -ge "$MAX_WAIT_INIT" ]; then
  echo "[run.sh] Timeout waiting for chroma-init to complete."
  exit 1
fi

# Wait for rag-app to be running
MAX_WAIT_APP=60
ELAPSED=0

echo "[run.sh] Waiting for rag-app service to be running..."
while [ "$ELAPSED" -lt "$MAX_WAIT_APP" ]; do
  if docker ps --format '{{.Names}} {{.Status}}' | grep -q '^rag-app '; then
    STATUS=$(docker inspect -f '{{.State.Status}}' rag-app)
    if [ "$STATUS" = "running" ]; then
      echo "[run.sh] rag-app is running."
      break
    fi
  fi
  sleep "$SLEEP_INTERVAL"
  ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

if [ "$ELAPSED" -ge "$MAX_WAIT_APP" ]; then
  echo "[run.sh] Timeout waiting for rag-app to start."
  exit 1
fi

# Simple health check with retries
HEALTH_URL="http://localhost:8000/health"
MAX_WAIT_HEALTH=30
ELAPSED=0

echo "[run.sh] Checking application health at $HEALTH_URL ..."
while [ "$ELAPSED" -lt "$MAX_WAIT_HEALTH" ]; do
  if curl -sSf "$HEALTH_URL" > /dev/null 2>&1; then
    echo "[run.sh] RAG API health check passed."
    break
  fi
  sleep 3
  ELAPSED=$((ELAPSED + 3))
done

if [ "$ELAPSED" -ge "$MAX_WAIT_HEALTH" ]; then
  echo "[run.sh] RAG API health check failed or timed out."
  exit 1
fi

# Test a sample query
echo "[run.sh] Sending sample query to /query endpoint..."
SAMPLE_PAYLOAD='{"query": "What is a proof-of-skills marketplace?", "top_k": 3}'

curl -sS -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d "$SAMPLE_PAYLOAD" || {
    echo "[run.sh] Sample query failed."
    exit 1
  }

echo "[run.sh] RAG pipeline appears to be operational."
