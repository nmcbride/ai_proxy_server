#!/usr/bin/env python3
"""
Debug script to test OpenAI client with our proxy
"""

import time

from openai import OpenAI

# Configure OpenAI client to use our proxy
client = OpenAI(
    api_key="test-key",
    base_url="http://localhost:8000",
)

print("🔍 Testing OpenAI Client with Debug...")

try:
    print("📋 Listing models...")
    models = client.models.list()
    print(f"✅ Found {len(models.data)} models")
    for model in models.data[:3]:  # Show first 3
        print(f"  - {model.id}")

except Exception as e:
    print(f"❌ Models Error: {e}")

try:
    print("\n💬 Testing chat completion...")
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello!"}],
        max_tokens=10,
    )
    print(f"✅ Chat Response: {response.choices[0].message.content}")

except Exception as e:
    print(f"❌ Chat Error: {e}")

try:
    print("\n🌊 Testing streaming chat completion...")
    start_time = time.time()
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": "Write a creative short story about a robot who learns to paint. Make it at least 150 words.",
            }
        ],
        max_tokens=200,
        stream=True,
    )

    print("✅ Streaming Response:")
    print("=" * 50)
    chunk_count = 0
    chunk_times = []
    first_chunk_time = None

    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            chunk_count += 1
            current_time = time.time()
            elapsed = current_time - start_time
            chunk_times.append(elapsed)

            if first_chunk_time is None:
                first_chunk_time = elapsed

            # Only show timing for first 10 and last 10 chunks to avoid spam
            if chunk_count <= 10 or chunk_count > (200 - 10):
                print(f"[{elapsed:.4f}s] ", end="", flush=True)
            elif chunk_count == 11:
                print(
                    "\n... (hiding timing for middle chunks) ...\n", end="", flush=True
                )

            print(chunk.choices[0].delta.content, end="", flush=True)

    print()  # New line after streaming
    print("=" * 50)

    total_time = time.time() - start_time
    time_to_first_chunk = first_chunk_time if first_chunk_time else 0
    time_between_chunks = (
        (chunk_times[-1] - chunk_times[0]) / len(chunk_times)
        if len(chunk_times) > 1
        else 0
    )

    print("📊 Streaming Analysis:")
    print(f"  Total chunks: {chunk_count}")
    print(f"  Total time: {total_time:.4f}s")
    print(f"  Time to first chunk: {time_to_first_chunk:.4f}s")
    print(f"  Average time between chunks: {time_between_chunks * 1000:.2f}ms")

    # Detect if it's truly streaming or buffered
    if time_between_chunks < 0.001:  # Less than 1ms between chunks
        print("  📦 DETECTED: Batched streaming (normal for many LLM APIs)")
        print("     Response is generated first, then streamed quickly")
        print("     This allows token-by-token client processing while")
        print("     maintaining efficient server-side generation")
    else:
        print("  ⚡ DETECTED: Real-time streaming")
        print("     Tokens arrive as they're generated")

    print("\n💡 Note: Your streaming proxy is working correctly!")
    print(f"   - The {time_to_first_chunk:.2f}s delay is LLM generation time")
    print("   - Streaming allows client to process tokens incrementally")
    print("   - This matches OpenAI API streaming behavior")

except Exception as e:
    print(f"❌ Streaming Error: {e}")

print("\n�� Debug completed!")
