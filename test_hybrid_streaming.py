#!/usr/bin/env python3
"""
Test script for hybrid streaming mode
Demonstrates tool calling + streaming final response
"""

import asyncio
import json
import time

import httpx


async def test_hybrid_streaming():
    """Test hybrid streaming with weather tool call"""
    
    # Test payload with tool call that should trigger hybrid mode
    payload = {
        "model": "gpt-4-turbo",
        "messages": [
            {
                "role": "user", 
                "content": "What's the weather like in Paris right now? Stream your response."
            }
        ],
        "stream": True,  # This will trigger hybrid streaming if enabled
        "max_tokens": 200,
    }
    
    print("🧪 Testing Hybrid Streaming Mode")
    print("=" * 50)
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    # Make request to proxy
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST",
            "http://localhost:8001/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
        ) as response:
            
            print(f"📡 Response Status: {response.status_code}")
            print(f"📡 Response Headers: {dict(response.headers)}")
            print()
            
            if response.status_code == 200:
                print("📨 Streaming Response:")
                print("-" * 30)
                
                chunk_count = 0
                first_chunk_time = None
                
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        if first_chunk_time is None:
                            first_chunk_time = time.time()
                            
                        chunk_count += 1
                        print(f"Chunk {chunk_count}: {chunk.strip()}")
                        
                        # Small delay to see streaming effect
                        await asyncio.sleep(0.01)
                
                end_time = time.time()
                
                print()
                print("⏱️  Timing Results:")
                print(f"   Total time: {end_time - start_time:.3f}s")
                if first_chunk_time:
                    print(f"   Time to first chunk: {first_chunk_time - start_time:.3f}s")
                print(f"   Total chunks received: {chunk_count}")
                
            else:
                error_content = await response.aread()
                print(f"❌ Error: {response.status_code}")
                print(f"   Content: {error_content.decode()}")


async def test_pure_streaming():
    """Test pure streaming (no tools) for comparison"""
    
    payload = {
        "model": "gpt-4-turbo", 
        "messages": [
            {
                "role": "user",
                "content": "Write a short poem about coding. Stream your response."
            }
        ],
        "stream": True,
        "max_tokens": 200,
    }
    
    print("\n\n🚀 Testing Pure Streaming Mode (No Tools)")
    print("=" * 50)
    
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST", 
            "http://localhost:8001/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
        ) as response:
            
            if response.status_code == 200:
                print("📨 Streaming Response:")
                print("-" * 30)
                
                chunk_count = 0
                first_chunk_time = None
                
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        if first_chunk_time is None:
                            first_chunk_time = time.time()
                            
                        chunk_count += 1
                        print(f"Chunk {chunk_count}: {chunk.strip()}")
                        await asyncio.sleep(0.01)
                
                end_time = time.time()
                
                print()
                print("⏱️  Timing Results:")
                print(f"   Total time: {end_time - start_time:.3f}s")
                if first_chunk_time:
                    print(f"   Time to first chunk: {first_chunk_time - start_time:.3f}s")
                print(f"   Total chunks received: {chunk_count}")


if __name__ == "__main__":
    print("🔧 Hybrid Streaming Test Suite")
    print("Make sure the server is running with ENABLE_HYBRID_STREAMING=true")
    print()
    
    asyncio.run(test_hybrid_streaming())
    asyncio.run(test_pure_streaming()) 