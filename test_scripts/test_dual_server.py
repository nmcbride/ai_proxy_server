#!/usr/bin/env python3
"""
Dual Server Test Script
Runs two AI Proxy Server instances to test both direct streaming and hybrid streaming modes simultaneously.

This script:
1. Starts two server instances on different ports with different configurations
2. Tests both modes with identical requests for proper performance comparison
3. Provides side-by-side performance and behavior analysis
4. Automatically cleans up both servers when done
"""

import asyncio
import json
import subprocess
import time
import httpx
import os
import signal
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# Test configuration
DIRECT_STREAMING_PORT = 8001
HYBRID_STREAMING_PORT = 8002
BASE_URL_DIRECT = f"http://localhost:{DIRECT_STREAMING_PORT}"
BASE_URL_HYBRID = f"http://localhost:{HYBRID_STREAMING_PORT}"

# Standard test requests for consistency
TEST_REQUESTS = {
    "simple_streaming": {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Count from 1 to 5, each number on a new line."}],
        "stream": True,
        "temperature": 0.3
    },
    "simple_non_streaming": {
        "model": "gpt-3.5-turbo", 
        "messages": [{"role": "user", "content": "Count from 1 to 5, each number on a new line."}],
        "stream": False,
        "temperature": 0.3
    },
    "tool_streaming": {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Use the get_debug_number tool to get a number and tell me what it is."}],
        "stream": True,
        "temperature": 0.3
    },
    "tool_non_streaming": {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Use the get_debug_number tool to get a number and tell me what it is."}],
        "stream": False,
        "temperature": 0.3
    },
    "complex_tool_test": {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Use both get_debug_number and get_call_counter tools, then tell me what numbers you got."}],
        "stream": True,
        "temperature": 0.3
    }
}

class ServerInstance:
    def __init__(self, name: str, port: int, enable_hybrid: bool):
        self.name = name
        self.port = port
        self.enable_hybrid = enable_hybrid
        self.process: Optional[subprocess.Popen] = None
        self.base_url = f"http://localhost:{port}"
        
    async def start(self):
        """Start the server instance with specific configuration."""
        print(f"🚀 Starting {self.name} on port {self.port}...")
        
        # Environment variables for this instance
        env = os.environ.copy()
        env["ENABLE_HYBRID_STREAMING"] = "true" if self.enable_hybrid else "false"
        env["PORT"] = str(self.port)
        
        # Start server process
        self.process = subprocess.Popen(
            ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(self.port)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group for clean shutdown
        )
        
        # Wait for server to be ready
        await self._wait_for_ready()
        print(f"✅ {self.name} ready on port {self.port}")
        
    async def _wait_for_ready(self, max_attempts: int = 30):
        """Wait for server to be ready to accept requests."""
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.base_url}/health", timeout=2.0)
                    if response.status_code == 200:
                        return
            except:
                pass
            await asyncio.sleep(1)
        raise Exception(f"Server {self.name} failed to start after {max_attempts} seconds")
        
    async def get_config(self) -> Dict[str, Any]:
        """Get server configuration."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/config")
            return response.json()
            
    def stop(self):
        """Stop the server instance."""
        if self.process:
            print(f"🛑 Stopping {self.name}...")
            try:
                # Kill the entire process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
            except:
                # Force kill if graceful shutdown fails
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except:
                    pass
            self.process = None

async def make_request(base_url: str, request_data: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
    """Make a request and return response data and timing."""
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        if request_data.get("stream", False):
            # Streaming request
            chunks = []
            chunk_times = []
            first_chunk_time = None
            
            async with client.stream(
                "POST",
                f"{base_url}/v1/chat/completions",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()
                
                async for chunk in response.aiter_lines():
                    if chunk.strip():
                        chunk_time = time.time()
                        if first_chunk_time is None:
                            first_chunk_time = chunk_time
                        
                        if chunk.startswith("data: ") and not chunk == "data: [DONE]":
                            try:
                                chunk_data = json.loads(chunk[6:])
                                chunks.append(chunk_data)
                                chunk_times.append(chunk_time - start_time)
                            except json.JSONDecodeError:
                                pass
            
            total_time = time.time() - start_time
            time_to_first_chunk = first_chunk_time - start_time if first_chunk_time else 0
            
            return {
                "type": "streaming",
                "chunks": len(chunks),
                "total_time": total_time,
                "time_to_first_chunk": time_to_first_chunk,
                "chunk_times": chunk_times
            }, total_time
            
        else:
            # Non-streaming request
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            total_time = time.time() - start_time
            response_data = response.json()
            
            return {
                "type": "non-streaming",
                "response": response_data,
                "total_time": total_time
            }, total_time

async def run_test_comparison():
    """Run comprehensive test comparison between direct and hybrid streaming modes."""
    print("=" * 80)
    print("🧪 DUAL SERVER AI PROXY TEST")
    print("=" * 80)
    print()
    
    print("ℹ️  Note: Assuming LiteLLM proxy container is running with API keys configured")
    print()
    
    # Initialize servers
    direct_server = ServerInstance("Direct Streaming Server", DIRECT_STREAMING_PORT, enable_hybrid=False)
    hybrid_server = ServerInstance("Hybrid Streaming Server", HYBRID_STREAMING_PORT, enable_hybrid=True)
    
    try:
        # Start both servers
        await asyncio.gather(
            direct_server.start(),
            hybrid_server.start()
        )
        
        # Get configurations
        print("📋 Server Configurations:")
        direct_config = await direct_server.get_config()
        hybrid_config = await hybrid_server.get_config()
        
        print(f"  Direct Server:  ENABLE_HYBRID_STREAMING = {direct_config.get('ENABLE_HYBRID_STREAMING')}")
        print(f"  Hybrid Server:  ENABLE_HYBRID_STREAMING = {hybrid_config.get('ENABLE_HYBRID_STREAMING')}")
        print()
        
        # Run all tests
        results = {}
        
        for test_name, request_data in TEST_REQUESTS.items():
            print(f"🔄 Running {test_name}...")
            
            # Test direct server
            direct_result, direct_time = await make_request(direct_server.base_url, request_data)
            
            # Test hybrid server  
            hybrid_result, hybrid_time = await make_request(hybrid_server.base_url, request_data)
            
            results[test_name] = {
                "direct": direct_result,
                "hybrid": hybrid_result,
                "request": request_data
            }
            
            # Show immediate comparison
            print(f"  Direct: {direct_time:.2f}s | Hybrid: {hybrid_time:.2f}s")
            print()
        
        # Print detailed analysis
        print_detailed_analysis(results)
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up servers
        direct_server.stop()
        hybrid_server.stop()
        print("\n✅ Cleanup complete")

def print_detailed_analysis(results: Dict[str, Dict[str, Any]]):
    """Print detailed performance and behavior analysis."""
    print("=" * 80)
    print("📊 DETAILED ANALYSIS")
    print("=" * 80)
    
    # Performance summary table
    print("\n🏁 Performance Summary:")
    print("-" * 80)
    print(f"{'Test':<25} {'Direct':<12} {'Hybrid':<12} {'Difference':<15} {'Winner'}")
    print("-" * 80)
    
    for test_name, result in results.items():
        direct_time = result["direct"]["total_time"]
        hybrid_time = result["hybrid"]["total_time"]
        diff = hybrid_time - direct_time
        winner = "Direct" if direct_time < hybrid_time else "Hybrid"
        
        print(f"{test_name:<25} {direct_time:<12.2f} {hybrid_time:<12.2f} {diff:<+15.2f} {winner}")
    
    print("-" * 80)
    
    # Behavior analysis
    print("\n🔍 Behavior Analysis:")
    
    for test_name, result in results.items():
        print(f"\n📋 {test_name}:")
        
        # Check if streaming behavior differs
        request_stream = result["request"].get("stream", False)
        has_tools = "tool" in test_name.lower()
        
        if request_stream:
            direct_chunks = result["direct"].get("chunks", 0)
            hybrid_chunks = result["hybrid"].get("chunks", 0)
            
            print(f"  Stream chunks: Direct={direct_chunks}, Hybrid={hybrid_chunks}")
            
            if has_tools:
                # For tool requests, hybrid should behave differently
                direct_ttfc = result["direct"].get("time_to_first_chunk", 0)
                hybrid_ttfc = result["hybrid"].get("time_to_first_chunk", 0)
                
                print(f"  Time to first chunk: Direct={direct_ttfc:.2f}s, Hybrid={hybrid_ttfc:.2f}s")
                
                if hybrid_ttfc > direct_ttfc * 1.5:
                    print("  ✅ Hybrid shows expected delay (tool calling phase)")
                else:
                    print("  ⚠️  Hybrid doesn't show expected tool calling delay")
        
        # Expected vs actual behavior
        if has_tools and request_stream:
            print(f"  Expected: Hybrid does tool calling then streams final response")
            print(f"  Expected: Direct skips tools and streams immediately")
        elif has_tools and not request_stream:
            print(f"  Expected: Both modes do tool calling, no streaming")
        else:
            print(f"  Expected: Both modes stream immediately, no tools")
    
    # Performance insights
    print("\n💡 Performance Insights:")
    
    # Simple streaming comparison
    simple_stream = results.get("simple_streaming")
    if simple_stream:
        direct_time = simple_stream["direct"]["total_time"]
        hybrid_time = simple_stream["hybrid"]["total_time"]
        print(f"  • Simple streaming: Direct={direct_time:.2f}s, Hybrid={hybrid_time:.2f}s")
        if abs(direct_time - hybrid_time) < 0.3:
            print("    ✅ Both modes have similar performance for simple requests")
        else:
            print("    ⚠️  Unexpected performance difference for simple requests")
    
    # Tool calling comparison
    tool_stream = results.get("tool_streaming")
    tool_non_stream = results.get("tool_non_streaming")
    if tool_stream and tool_non_stream:
        hybrid_stream_time = tool_stream["hybrid"]["total_time"]
        hybrid_non_stream_time = tool_non_stream["hybrid"]["total_time"]
        print(f"  • Hybrid tool calling: Stream={hybrid_stream_time:.2f}s, Non-stream={hybrid_non_stream_time:.2f}s")
        if hybrid_stream_time < hybrid_non_stream_time:
            print("    ✅ Hybrid streaming faster than non-streaming for tools")
        else:
            print("    ⚠️  Hybrid streaming not faster than non-streaming for tools")

def main():
    """Main entry point."""
    try:
        asyncio.run(run_test_comparison())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main() 