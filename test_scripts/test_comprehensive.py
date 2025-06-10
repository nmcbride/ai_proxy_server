#!/usr/bin/env python3
"""
Comprehensive Test Suite for AI Proxy Server
Tests all modes with identical requests for proper performance comparison
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Optional

import httpx


class TestResult:
    def __init__(self, name: str, success: bool, message: str, duration: float = 0.0, details: Optional[Dict] = None):
        self.name = name
        self.success = success
        self.message = message
        self.duration = duration
        self.details = details or {}


class ComprehensiveTestSuite:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.server_config = {}
        
    async def run_all_tests(self):
        """Run all test scenarios"""
        print("🚀 AI Proxy Server Comprehensive Test Suite")
        print("=" * 60)
        print()
        
        # Check server availability and get config
        if not await self.check_server_health():
            print("❌ Server is not available. Please start the server first.")
            return
            
        # Get server configuration to understand current mode
        await self.get_server_configuration()
        
        # Run tests with identical requests for proper comparison
        await self.test_identical_tool_requests()
        await self.test_identical_non_tool_requests() 
        await self.test_behavior_validation()
        
        # Print final results
        self.print_summary()
        
    async def check_server_health(self) -> bool:
        """Check if the server is running and responsive"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/mcp/status")
                if response.status_code == 200:
                    status = response.json()
                    print(f"✅ Server is running - {status.get('connected_servers', 0)} MCP servers, {status.get('total_tools', 0)} tools")
                    return True
        except Exception as e:
            print(f"❌ Server health check failed: {e}")
            
        return False
        
    async def get_server_configuration(self):
        """Get current server configuration from running server"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/config")
                if response.status_code == 200:
                    config = response.json()
                    print("🔧 Actual Server Configuration:")
                    print(f"   ENABLE_HYBRID_STREAMING: {config.get('ENABLE_HYBRID_STREAMING', 'unknown')}")
                    print(f"   MAX_TOOL_ROUNDS: {config.get('MAX_TOOL_ROUNDS', 'unknown')}")
                    print(f"   TOOL_EXECUTION_TIMEOUT: {config.get('TOOL_EXECUTION_TIMEOUT', 'unknown')}")
                    print()
                    
                    self.server_config['hybrid_streaming'] = config.get('ENABLE_HYBRID_STREAMING', False)
                    return
                    
        except Exception as e:
            print(f"⚠️  Could not get server config: {e}")
            
        # Fallback to environment variables
        hybrid_streaming = os.getenv('ENABLE_HYBRID_STREAMING', 'false').lower() == 'true'
        print("🔧 Fallback Configuration (test environment):")
        print(f"   ENABLE_HYBRID_STREAMING: {hybrid_streaming}")
        print(f"   MAX_TOOL_ROUNDS: {os.getenv('MAX_TOOL_ROUNDS', '5')}")
        print(f"   TOOL_EXECUTION_TIMEOUT: {os.getenv('TOOL_EXECUTION_TIMEOUT', '30.0')}")
        print("   ⚠️  Note: Using test environment, may not match running server")
        print()
        
        self.server_config['hybrid_streaming'] = hybrid_streaming
        
    async def test_identical_tool_requests(self):
        """Test tool requests with identical payloads across different modes"""
        print("🔧 Testing Identical Tool Requests (Performance Comparison)")
        print("-" * 60)
        
        # Use identical request that should trigger tools
        tool_payload = {
            "model": "gpt-4-turbo",
            "messages": [
                {"role": "user", "content": "Use the get_debug_number tool to get the debug number, then tell me what it is."}
            ],
            "max_tokens": 150,
        }
        
        # Test 1: Non-streaming with tools
        test_payload = {**tool_payload, "stream": False}
        result = await self.make_request("Non-streaming with tools", test_payload)
        if result.success and ("42" in result.message or "debug" in result.message.lower()):
            result.details["tools_used"] = "✅ Tools executed"
        else:
            result.details["tools_used"] = "❌ Tools not detected"
        self.results.append(result)
        
        # Test 2: Streaming request (behavior depends on ENABLE_HYBRID_STREAMING)
        test_payload = {**tool_payload, "stream": True}
        result = await self.make_streaming_request("Streaming with tool request", test_payload)
        
        # Analyze behavior based on server config
        if self.server_config.get('hybrid_streaming', False):
            # Should execute tools then stream
            if result.duration > 2.0:
                result.details["behavior"] = "✅ Hybrid streaming (tools + streaming)"
            else:
                result.details["behavior"] = "⚠️  Too fast for tool execution"
        else:
            # Should skip tools and stream directly
            if result.duration < 2.0:
                result.details["behavior"] = "✅ Direct streaming (tools skipped)"
            else:
                result.details["behavior"] = "⚠️  Too slow for direct streaming"
                
        if "42" in result.message:
            result.details["tools_used"] = "✅ Tools executed"
        else:
            result.details["tools_used"] = "❌ No tool results detected"
            
        self.results.append(result)
        
    async def test_identical_non_tool_requests(self):
        """Test requests that don't need tools"""
        print("\n📝 Testing Identical Non-Tool Requests")
        print("-" * 60)
        
        # Use identical request that shouldn't trigger tools
        simple_payload = {
            "model": "gpt-4-turbo",
            "messages": [
                {"role": "user", "content": "Write exactly 3 words about coding."}
            ],
            "max_tokens": 50,
        }
        
        # Test 1: Non-streaming
        test_payload = {**simple_payload, "stream": False}
        result = await self.make_request("Non-streaming simple", test_payload)
        self.results.append(result)
        
        # Test 2: Streaming
        test_payload = {**simple_payload, "stream": True}
        result = await self.make_streaming_request("Streaming simple", test_payload)
        self.results.append(result)
        
    async def test_behavior_validation(self):
        """Validate that server behavior matches configuration"""
        print("\n🔍 Behavior Validation Tests")
        print("-" * 60)
        
        # Test explicit tool usage to validate hybrid streaming behavior
        explicit_tool_payload = {
            "model": "gpt-4-turbo",
            "messages": [
                {"role": "user", "content": "Call get_debug_number and get_call_counter tools, then tell me the results. Stream your response."}
            ],
            "stream": True,
            "max_tokens": 200,
        }
        
        start_time = time.time()
        result = await self.make_streaming_request("Behavior validation", explicit_tool_payload)
        
        # Validate behavior matches expectations
        expected_behavior = "hybrid" if self.server_config.get('hybrid_streaming', False) else "direct"
        actual_behavior = "unknown"
        
        if "42" in result.message and result.duration > 2.0:
            actual_behavior = "hybrid"
        elif "42" not in result.message and result.duration < 2.0:
            actual_behavior = "direct"
        elif "42" in result.message and result.duration < 2.0:
            actual_behavior = "hybrid_fast"
        else:
            actual_behavior = "unexpected"
            
        result.details["expected"] = expected_behavior
        result.details["actual"] = actual_behavior
        result.details["match"] = "✅" if expected_behavior == actual_behavior or (expected_behavior == "hybrid" and actual_behavior == "hybrid_fast") else "❌"
        
        self.results.append(result)
        
    async def make_request(self, test_name: str, payload: Dict) -> TestResult:
        """Make a non-streaming request and return result"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if "choices" in result and result["choices"]:
                        message = result["choices"][0]["message"]
                        content = message.get("content", "")
                        
                        # Check for any remaining tool calls (shouldn't happen)
                        if message.get("tool_calls"):
                            return TestResult(
                                test_name, 
                                False, 
                                "Got tool calls instead of final response",
                                duration,
                                {"tool_calls": len(message["tool_calls"])}
                            )
                        
                        # Success
                        print(f"✅ {test_name}: {duration:.2f}s")
                        print(f"   Response: {content[:80]}{'...' if len(content) > 80 else ''}")
                            
                        return TestResult(
                            test_name,
                            True,
                            content,
                            duration,
                            {"tokens": result.get("usage", {}).get("total_tokens", 0)}
                        )
                    else:
                        return TestResult(test_name, False, "No choices in response", duration)
                else:
                    error_content = await response.aread()
                    return TestResult(test_name, False, f"HTTP {response.status_code}: {error_content.decode()[:200]}", duration)
                    
        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ {test_name}: {str(e)}")
            return TestResult(test_name, False, str(e), duration)
            
    async def make_streaming_request(self, test_name: str, payload: Dict) -> TestResult:
        """Make a streaming request and return result"""
        start_time = time.time()
        first_chunk_time = None
        chunk_count = 0
        full_content = ""
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                ) as response:
                    
                    if response.status_code == 200:
                        async for chunk in response.aiter_text():
                            if chunk.strip():
                                if first_chunk_time is None:
                                    first_chunk_time = time.time()
                                    
                                chunk_count += 1
                                
                                # Try to parse SSE data
                                if chunk.startswith("data: "):
                                    data_part = chunk[6:].strip()
                                    if data_part and data_part != "[DONE]":
                                        try:
                                            chunk_json = json.loads(data_part)
                                            if "choices" in chunk_json and chunk_json["choices"]:
                                                delta = chunk_json["choices"][0].get("delta", {})
                                                if "content" in delta:
                                                    full_content += delta["content"]
                                        except json.JSONDecodeError:
                                            pass
                        
                        duration = time.time() - start_time
                        time_to_first = first_chunk_time - start_time if first_chunk_time else 0
                        
                        print(f"✅ {test_name}: {duration:.2f}s ({chunk_count} chunks, {time_to_first:.2f}s to first)")
                        print(f"   Content: {full_content[:80]}{'...' if len(full_content) > 80 else ''}")
                        
                        return TestResult(
                            test_name,
                            True,
                            full_content,
                            duration,
                            {
                                "chunks": chunk_count,
                                "time_to_first_chunk": time_to_first,
                                "average_chunk_time": duration / chunk_count if chunk_count > 0 else 0
                            }
                        )
                    else:
                        error_content = await response.aread()
                        duration = time.time() - start_time
                        return TestResult(test_name, False, f"HTTP {response.status_code}: {error_content.decode()[:200]}", duration)
                        
        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ {test_name}: {str(e)}")
            return TestResult(test_name, False, str(e), duration)
            
    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        success_count = sum(1 for r in self.results if r.success)
        total_count = len(self.results)
        
        print(f"Overall: {success_count}/{total_count} tests passed")
        print()
        
        # Performance comparison for identical requests
        tool_tests = [r for r in self.results if "with tools" in r.name or "tool request" in r.name]
        simple_tests = [r for r in self.results if "simple" in r.name]
        
        if tool_tests:
            print("🔧 Tool Request Performance:")
            for test in tool_tests:
                status = "✅" if test.success else "❌"
                print(f"  {status} {test.name}: {test.duration:.2f}s")
                for key, value in test.details.items():
                    print(f"     {key}: {value}")
            print()
            
        if simple_tests:
            print("📝 Simple Request Performance:")
            for test in simple_tests:
                status = "✅" if test.success else "❌"
                print(f"  {status} {test.name}: {test.duration:.2f}s")
            print()
                
        # Behavior validation
        validation_tests = [r for r in self.results if "validation" in r.name]
        if validation_tests:
            print("🔍 Behavior Validation:")
            for test in validation_tests:
                status = "✅" if test.success else "❌"
                print(f"  {status} {test.name}: {test.duration:.2f}s")
                for key, value in test.details.items():
                    print(f"     {key}: {value}")
            print()
            
        # Performance insights
        print("📈 Performance Insights:")
        non_streaming_times = [r.duration for r in self.results if "Non-streaming" in r.name and r.success]
        streaming_times = [r.duration for r in self.results if "Streaming" in r.name and r.success]
        
        if non_streaming_times:
            avg_non_streaming = sum(non_streaming_times) / len(non_streaming_times)
            print(f"  • Average non-streaming: {avg_non_streaming:.2f}s")
            
        if streaming_times:
            avg_streaming = sum(streaming_times) / len(streaming_times)
            print(f"  • Average streaming: {avg_streaming:.2f}s")
            
        # Expected vs actual performance order
        print()
        print("💡 Expected Performance Order (fastest to slowest):")
        print("  1. Streaming simple requests (no tools)")
        print("  2. Non-streaming simple requests")
        print("  3. Direct streaming with tool requests (tools skipped)")
        print("  4. Non-streaming with tools")
        print("  5. Hybrid streaming with tools (tool execution + streaming)")


async def main():
    """Run the comprehensive test suite"""
    suite = ComprehensiveTestSuite()
    await suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main()) 