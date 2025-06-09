#!/usr/bin/env python3
"""
Debug script to test real-time streaming behavior
"""

import asyncio
import time
import httpx
from typing import AsyncGenerator

print("🔍 Testing Real-Time Streaming with Raw HTTP...")

async def test_streaming():
    """Test streaming with raw HTTP to see real chunk timings"""
    
    url = "http://localhost:8000/v1/chat/completions"
    headers = {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Write a creative short story about a robot who learns to paint. Make it at least 150 words."}],
        "max_tokens": 200,
        "stream": True
    }
    
    start_time = time.time()
    chunk_times = []
    chunk_count = 0
    
    print("🌊 Starting streaming request...")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST", 
                url, 
                headers=headers, 
                json=payload, 
                timeout=30.0
            ) as response:
                
                if response.status_code != 200:
                    print(f"❌ Error: HTTP {response.status_code}")
                    print(await response.aread())
                    return
                
                print(f"✅ Response started at {time.time() - start_time:.4f}s")
                print("📡 Receiving chunks...")
                
                buffer = ""
                async for chunk_bytes in response.aiter_bytes(chunk_size=1):
                    current_time = time.time()
                    elapsed = current_time - start_time
                    
                    if chunk_bytes:
                        chunk_count += 1
                        chunk_times.append(elapsed)
                        
                        # Show timing every 100 bytes to see real patterns
                        if chunk_count % 100 == 0:
                            print(f"[{elapsed:.4f}s] Received {chunk_count} bytes", flush=True)
                
                print("\n" + "=" * 60)
                
                total_time = time.time() - start_time
                if len(chunk_times) > 1:
                    first_chunk = chunk_times[0]
                    last_chunk = chunk_times[-1]
                    streaming_duration = last_chunk - first_chunk
                    avg_chunk_interval = streaming_duration / len(chunk_times) if len(chunk_times) > 1 else 0
                    
                    print(f"📊 Raw HTTP Streaming Analysis:")
                    print(f"  Total bytes received: {chunk_count}")
                    print(f"  Total time: {total_time:.4f}s")
                    print(f"  Time to first byte: {first_chunk:.4f}s")
                    print(f"  Time to last byte: {last_chunk:.4f}s")
                    print(f"  Streaming duration: {streaming_duration:.4f}s")
                    print(f"  Average interval: {avg_chunk_interval * 1000:.2f}ms per byte")
                    
                    if streaming_duration > 0.1:  # If streaming took more than 100ms
                        print("  ✅ DETECTED: Real streaming (bytes arrived over time)")
                    else:
                        print("  🚨 DETECTED: Buffered response (all bytes arrived at once)")
                        
        except Exception as e:
            print(f"❌ Error: {e}")

print("Starting async test...")
asyncio.run(test_streaming())
print("\n🎯 Real-time streaming test completed!") 