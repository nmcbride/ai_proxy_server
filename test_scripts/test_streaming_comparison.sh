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
"messages": [{"role": "user", "content": "Say hello in exactly 5 words."}],
"stream": false,
"max_tokens": 20
}' \
--max-time 10 \
-w "\n📊 Non-streaming - Total time: %{time_total}s\n"

echo -e "\n================================================"

echo "2️⃣ Testing STREAMING response (through proxy)..."
echo "Starting streaming at: $(date '+%H:%M:%S.%3N')"

echo "📡 Showing first 8 lines of streaming response:"
curl -X POST "http://localhost:8000/v1/chat/completions" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer test-key" \
-d '{
"model": "gpt-3.5-turbo", 
"messages": [{"role": "user", "content": "Say hello in exactly 5 words."}],
"stream": true,
"max_tokens": 20
}' \
--no-buffer \
--max-time 10 | head -8

echo -e "\n✅ Streaming test completed (showing first 8 chunks)"

echo -e "\n================================================"
echo "🎯 Comparison completed!"
echo ""
echo "🧠 Key Observations:"
echo "   • Non-streaming: Single JSON response with complete message"
echo "   • Streaming: Multiple SSE chunks with 'data:' prefix"
echo "   • Both should complete without hanging"
echo "   • Streaming enables real-time progressive display" 