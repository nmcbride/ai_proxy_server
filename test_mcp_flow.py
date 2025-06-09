#!/usr/bin/env python3
"""
Test script for MCP tool calling flow
"""

import asyncio
import json

import httpx


async def test_mcp_flow():
    """Test the MCP tool calling flow"""
    
    # Start the proxy server first (run separately)
    proxy_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # 1. Check MCP status
        print("🔍 Checking MCP status...")
        try:
            response = await client.get(f"{proxy_url}/mcp/status")
            if response.status_code == 200:
                status = response.json()
                print(f"✅ Connected servers: {status.get('connected_servers', 0)}")
                print(f"✅ Available tools: {status.get('total_tools', 0)}")
                for tool in status.get('tools', []):
                    print(f"   - {tool['name']}: {tool['description'][:100]}...")
            else:
                print(f"❌ MCP status failed: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ Could not connect to proxy: {e}")
            return
        
        # 2. Test chat completion with weather tools
        print("\n🌤️ Testing weather tool...")
        
        weather_request = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "user", 
                    "content": "What's the weather like in New York? Please give me the current conditions."
                }
            ],
            "temperature": 0.7
        }
        
        await run_test_request(client, proxy_url, weather_request, "Weather test")
        
        # 3. Test Context7 tools
        print("\n📚 Testing Context7 documentation tools...")
        
        context7_request = {
            "model": "gpt-4-turbo", 
            "messages": [
                {
                    "role": "user",
                    "content": "Find basic info about the requests library. Just the main usage, keep it brief."
                }
            ],
            "temperature": 0.7
        }
        
        await run_detailed_test_request(client, proxy_url, context7_request, "Context7 brief test")
        
        # 4. Test Context7 with explicit mention
        print("\n📚 Testing Context7 with explicit instruction...")
        
        context7_explicit_request = {
            "model": "gpt-4-turbo",
            "messages": [
                {
                    "role": "user", 
                    "content": "Use Context7 to find documentation for React hooks. I need examples of useState and useEffect."
                }
            ],
            "temperature": 0.7
        }
        
        await run_test_request(client, proxy_url, context7_explicit_request, "Context7 explicit test")


async def run_test_request(client, proxy_url, test_request, test_name):
    """Helper function to run a test request"""
    try:
        response = await client.post(
            f"{proxy_url}/v1/chat/completions",
            json=test_request,
            headers={"Content-Type": "application/json"},
            timeout=30.0  # 30 second timeout
        )
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Check if we got a final answer (not tool calls)
            if "choices" in result and result["choices"]:
                message = result["choices"][0]["message"]
                if message.get("tool_calls"):
                    print("❌ Still got tool calls instead of final answer")
                    print("Tool calls:", json.dumps(message["tool_calls"], indent=2))
                else:
                    print("✅ Got final answer:")
                    content = message.get('content', 'No content')
                    # Truncate long responses for readability
                    if len(content) > 200:
                        print(f"Assistant: {content[:200]}...")
                    else:
                        print(f"Assistant: {content}")
                    
                    # Check usage stats
                    if "usage" in result:
                        usage = result["usage"]
                        print(f"📊 Tokens used: {usage.get('total_tokens', 0)} " +
                              f"(prompt: {usage.get('prompt_tokens', 0)}, " +
                              f"completion: {usage.get('completion_tokens', 0)})")
            else:
                print("❌ No choices in response")
                print(f"Raw response: {result}")
        else:
            print(f"❌ {test_name} failed: {response.status_code}")
            try:
                error_details = response.json()
                print(f"Error details: {json.dumps(error_details, indent=2)}")
            except:
                print(f"Raw error response: {response.text}")
            
    except httpx.TimeoutException:
        print(f"❌ {test_name} timed out (>30s)")
    except httpx.RequestError as e:
        print(f"❌ Network error: {e}")
    except Exception as e:
        print(f"❌ {test_name} error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
    
    print()  # Add spacing between tests


async def run_detailed_test_request(client, proxy_url, test_request, test_name):
    """Helper function to run a test request with detailed tool call logging"""
    try:
        response = await client.post(
            f"{proxy_url}/v1/chat/completions",
            json=test_request,
            headers={"Content-Type": "application/json"},
            timeout=60.0  # Longer timeout for Context7
        )
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Check if we got a final answer (not tool calls)
            if "choices" in result and result["choices"]:
                message = result["choices"][0]["message"]
                if message.get("tool_calls"):
                    print("❌ Still got tool calls instead of final answer")
                    print("Remaining tool calls:")
                    for tool_call in message["tool_calls"]:
                        print(f"  - {tool_call['function']['name']}: {tool_call['function'].get('arguments', {})}")
                else:
                    print("✅ Got final answer:")
                    content = message.get('content', 'No content')
                    
                    # Look for Context7 patterns in the response
                    if "Selected Library" in content or "library ID" in content or "/tiangolo/fastapi" in content:
                        print("🔍 Context7 patterns detected in response")
                    
                    # Show first part of response
                    if len(content) > 300:
                        print(f"Assistant: {content[:300]}...")
                    else:
                        print(f"Assistant: {content}")
                    
                    # Check usage stats - Context7 should use many tokens if it got docs
                    if "usage" in result:
                        usage = result["usage"]
                        total_tokens = usage.get('total_tokens', 0)
                        print(f"📊 Tokens used: {total_tokens} " +
                              f"(prompt: {usage.get('prompt_tokens', 0)}, " +
                              f"completion: {usage.get('completion_tokens', 0)})")
                        
                        if total_tokens > 2000:
                            print("✅ High token usage suggests real documentation was retrieved")
                        else:
                            print("⚠️ Low token usage - may not have retrieved full documentation")
            else:
                print("❌ No choices in response")
                print(f"Raw response: {result}")
        else:
            print(f"❌ {test_name} failed: {response.status_code}")
            try:
                error_details = response.json()
                print(f"Error details: {json.dumps(error_details, indent=2)}")
            except:
                print(f"Raw error response: {response.text}")
            
    except httpx.TimeoutException:
        print(f"❌ {test_name} timed out (>60s)")
    except httpx.RequestError as e:
        print(f"❌ Network error: {e}")
    except Exception as e:
        print(f"❌ {test_name} error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
    
    print()  # Add spacing between tests


if __name__ == "__main__":
    print("🚀 Testing MCP Tool Calling Flow")
    print("=" * 40)
    asyncio.run(test_mcp_flow()) 