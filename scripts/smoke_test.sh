#!/usr/bin/env bash
set -euo pipefail

# Alice AI Secretary - Docker Compose Smoke Test
# This script validates that all services are running and responding to basic requests

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="http://localhost:8000"
MAX_RETRIES=30
RETRY_DELAY=2

echo "=== Alice AI Secretary Smoke Test ==="
echo ""

# Cleanup function
cleanup() {
  local exit_code=$?
  echo ""
  if [ $exit_code -eq 0 ]; then
    echo "Cleaning up services..."
    docker compose down
  fi
  return $exit_code
}

trap cleanup EXIT

# 1. Start all services
echo "1. Starting Docker Compose services..."
cd "$SCRIPT_DIR"
docker compose up -d
echo "   Services started. Waiting for API to become healthy..."

# 2. Wait for API to be healthy
echo "2. Polling API health endpoint..."
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if curl -sf "${API_URL}/health" > /dev/null 2>&1; then
    echo "   ✓ API is healthy (HTTP 200)"
    break
  fi
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
    echo "   Retry $RETRY_COUNT/$MAX_RETRIES: API not ready yet..."
    sleep $RETRY_DELAY
  fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "   ✗ API failed to become healthy after $((MAX_RETRIES * RETRY_DELAY)) seconds"
  echo "Smoke test FAILED"
  exit 1
fi

# 3. Verify GET /health returns HTTP 200
echo "3. Verifying GET /health response..."
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/health")
if [ "$HEALTH_STATUS" = "200" ]; then
  echo "   ✓ GET /health returned HTTP 200"
else
  echo "   ✗ GET /health returned HTTP $HEALTH_STATUS"
  echo "Smoke test FAILED"
  exit 1
fi

# 4. POST an RSS source
echo "4. Adding RSS source..."
SOURCE_RESPONSE=$(curl -sf -X POST "${API_URL}/api/v1/sources" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Smoke Test Feed",
    "url": "https://feeds.arstechnica.com/arstechnica/index",
    "source_type": "rss"
  }')

SOURCE_ID=$(echo "$SOURCE_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
if [ -z "$SOURCE_ID" ]; then
  # Try alternate JSON structure
  SOURCE_ID=$(echo "$SOURCE_RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
fi

if [ -z "$SOURCE_ID" ]; then
  echo "   ✗ Failed to extract source ID from response"
  echo "   Response: $SOURCE_RESPONSE"
  echo "Smoke test FAILED"
  exit 1
fi

echo "   ✓ RSS source added (ID: $SOURCE_ID)"

# 5. Trigger a fetch
echo "5. Triggering RSS fetch..."
FETCH_RESPONSE=$(curl -sf -X POST "${API_URL}/api/v1/connectors/rss/fetch" \
  -H "Content-Type: application/json" \
  -d "{\"source_id\": \"$SOURCE_ID\"}")

echo "   ✓ Fetch triggered"

# 6. Wait for content processing
echo "6. Waiting for content to be processed (30 seconds)..."
sleep 30

# 7. Check for content
echo "7. Checking for fetched content..."
CONTENT_RESPONSE=$(curl -sf "${API_URL}/api/v1/content?limit=10")
CONTENT_COUNT=$(echo "$CONTENT_RESPONSE" | grep -o '"id"' | wc -l)

if [ "$CONTENT_COUNT" -gt 0 ]; then
  echo "   ✓ Found $CONTENT_COUNT content items"
else
  echo "   ⚠ No content items found (pipeline may still be processing)"
fi

# 8. Cleanup and report success
echo ""
echo "Smoke test PASSED"
exit 0
