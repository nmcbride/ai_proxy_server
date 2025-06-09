#!/bin/bash

echo "🔍 Testing Streaming vs Non-Streaming Comparison..."
echo "================================================"

echo "1️⃣ Testing NON-STREAMING response (through proxy)..."
echo "Starting non-streaming at: $(date '+%H:%M:%S.%3N')"

curl -X POST "http://localhost:8000/v1/chat/completions" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer test-key" \
-d '{
"model": "gpt-3.5-turbo",
"messages": [{"role": "user", "content": "Write exactly 3 sentences about robots."}],
"stream": false,
"max_tokens": 100
}' \
--no-buffer \
-w "\n📊 Non-streaming - Total time: %{time_total}s, Time to first byte: %{time_starttransfer}s\n" \
-s | jq -r '.choices[0].message.content' 2>/dev/null || cat

echo -e "\n================================================"

echo "2️⃣ Testing STREAMING response (through proxy)..."
echo "Starting streaming at: $(date '+%H:%M:%S.%3N')"

curl -X POST "http://localhost:8000/v1/chat/completions" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer test-key" \
-d '{
"model": "gpt-3.5-turbo", 
"messages": [{"role": "user", "content": "Write exactly 3 sentences about robots."}],
"stream": true,
"max_tokens": 100
}' \
--no-buffer \
-w "\n📊 Streaming - Total time: %{time_total}s, Time to first byte: %{time_starttransfer}s\n" | \
while IFS= read -r line; do
    if [[ $line == data:* ]]; then
        # Parse SSE data line and extract content
        json_part=$(echo "$line" | sed 's/^data: //')
        if [[ $json_part != "[DONE]" ]]; then
            content=$(echo "$json_part" | jq -r '.choices[0].delta.content // empty' 2>/dev/null)
            if [[ -n "$content" && "$content" != "null" ]]; then
                echo -n "$content"
            fi
        fi
    else
        # Non-data lines (timing info, etc.)
        if [[ $line == *"Total time"* ]]; then
            echo -e "\n$line"
        fi
    fi
done

echo -e "\n================================================"
echo "🎯 Comparison completed!"
echo ""
echo "🧠 Key Differences:"
echo "   • Non-streaming: Single response after full generation"
echo "   • Streaming: Multiple chunks allowing real-time processing"
echo "   • Both should have similar total times"
echo "   • Streaming enables progressive UI updates" 