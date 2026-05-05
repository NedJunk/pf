#!/bin/bash
set -e

# Gemini Models Script
# Lists available Gemini models via the REST API.
# Requires GEMINI_API_KEY to be set.
# Caches response to /tmp/gemini-models-cache.json (24-hour TTL).

CACHE_FILE="/tmp/gemini-models-cache.json"
CACHE_MAX_AGE=$((24 * 60 * 60))  # 24 hours in seconds

if [[ -z "$GEMINI_API_KEY" ]]; then
  echo "Error: GEMINI_API_KEY is not set" >&2
  exit 1
fi

# Check if cache is fresh
if [[ -f "$CACHE_FILE" ]]; then
  file_age=$(($(date +%s) - $(stat -f%m "$CACHE_FILE" 2>/dev/null || echo 0)))
  if [[ $file_age -lt $CACHE_MAX_AGE ]]; then
    cat "$CACHE_FILE"
    exit 0
  fi
fi

# Fetch from API and cache
response=$(curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY")
echo "$response" > "$CACHE_FILE"
echo "$response"

# Parse and print model names
if command -v jq &> /dev/null; then
  echo "$response" | jq -r '.models[].name' | sed 's/^models\///'
else
  echo "Note: jq not available; raw JSON above" >&2
fi
