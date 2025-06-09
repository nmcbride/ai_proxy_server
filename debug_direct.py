#!/usr/bin/env python3
"""
Debug script to test direct connection to LiteLLM (bypassing our proxy)
"""

from openai import OpenAI
import time

# Get the LiteLLM URL from config or use default
LITELLM_BASE_URL = "http://localhost:4000"  # Default LiteLLM port

# Configure OpenAI client to connect DIRECTLY to LiteLLM
client = OpenAI(
    api_key="test-key",
    base_url=LITELLM_BASE_URL,
)

print("🔍 Testing DIRECT connection to LiteLLM...")

try:
    print("\n🌊 Testing streaming chat completion (DIRECT to LiteLLM)...")
    start_time = time.time()
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Write a creative short story about a robot who learns to paint. Make it at least 150 words."}],
        max_tokens=200,
        stream=True
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
                print(f"\n... (hiding timing for middle chunks) ...\n", end="", flush=True)
            
            print(chunk.choices[0].delta.content, end="", flush=True)
    
    print()  # New line after streaming
    print("=" * 50)
    
    total_time = time.time() - start_time
    time_to_first_chunk = first_chunk_time if first_chunk_time else 0
    time_between_chunks = (chunk_times[-1] - chunk_times[0]) / len(chunk_times) if len(chunk_times) > 1 else 0
    
    print(f"📊 DIRECT LiteLLM Analysis:")
    print(f"  Total chunks: {chunk_count}")
    print(f"  Total time: {total_time:.4f}s")
    print(f"  Time to first chunk: {time_to_first_chunk:.4f}s")
    print(f"  Average time between chunks: {time_between_chunks * 1000:.2f}ms")
    
    # Detect if it's truly streaming or buffered
    if time_between_chunks < 0.001:  # Less than 1ms between chunks
        print("  🚨 DETECTED: Buffered response (not true streaming)")
        print("     All chunks arrived within milliseconds of each other")
        print("     This suggests LiteLLM itself is buffering the response")
    else:
        print("  ✅ DETECTED: True streaming response")
        print("     The issue is in our proxy, not LiteLLM")
    
except Exception as e:
    print(f"❌ Direct LiteLLM Error: {e}")
    print("Make sure LiteLLM is running on localhost:4000")

print("\n🎯 Direct LiteLLM test completed!") 