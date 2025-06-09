#!/bin/bash

echo "🔍 Testing PROXY Streaming with curl..."
echo "================================================"

# Test streaming through our proxy
echo "🌊 Testing streaming chat completions through PROXY..."
echo "Starting request at: $(date '+%H:%M:%S.%3N')"

curl -X POST "http://localhost:8000/v1/chat/completions" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer test-key" \
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
echo "🎯 Proxy streaming test completed!"
echo ""
echo "💡 Compare the timestamps above with the direct LiteLLM test!"
echo "   If streaming is working, you should see similar timing patterns." 