#!/usr/bin/env python3
"""
Minimal proxy test to isolate streaming issues
"""

import asyncio
import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI()

@app.post("/test-stream")
async def test_stream():
    """Minimal streaming proxy test"""
    
    # Direct request to LiteLLM with minimal setup
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method="POST",
            url="http://localhost:4000/v1/chat/completions",
            headers={
                "Authorization": "Bearer sk-litellm-default-key",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Count from 1 to 5"}],
                "stream": True,
                "max_tokens": 30
            },
            stream=True  # This is the key!
        )
        
        async def stream_generator():
            try:
                async for line in response.aiter_lines():
                    if line.strip():
                        yield (line + "\n").encode()
            finally:
                await response.aclose()
        
        return StreamingResponse(
            stream_generator(),
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="text/plain"
        )

if __name__ == "__main__":
    print("🧪 Starting minimal streaming proxy test on port 9000...")
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info") 