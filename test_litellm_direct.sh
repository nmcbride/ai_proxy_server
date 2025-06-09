#!/bin/bash

echo "🔍 Testing LiteLLM Streaming DIRECTLY with curl..."
echo "================================================"

# Test basic health first
echo "1️⃣ Testing LiteLLM health..."
curl -s -H "Authorization: Bearer sk-litellm-default-key" http://localhost:4000/health
echo -e "\n"

# Test streaming with timing
echo "2️⃣ Testing streaming chat completions..."
echo "Starting request at: $(date '+%H:%M:%S.%3N')"

curl -X POST "http://localhost:4000/v1/chat/completions" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer sk-litellm-default-key" \
-d '{
"model": "gpt-3.5-turbo",
"messages": [{"role": "user", "content": "Count from 1 to 10 slowly"}],
"stream": true,
"max_tokens": 50
}' \
--no-buffer \
-w "\n\nTotal time: %{time_total}s\nTime to first byte: %{time_starttransfer}s\n" | \
while IFS= read -r line; do
    echo "[$(date '+%H:%M:%S.%3N')] $line"
done

echo "================================================"
echo "🎯 Direct LiteLLM test completed!" 