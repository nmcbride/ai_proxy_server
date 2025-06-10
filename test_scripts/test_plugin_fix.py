#!/usr/bin/env python3
"""
Test to verify debug plugin works with TESTWORD instead of PYTHON
to avoid triggering MCP tool calls.
"""

import httpx
import json

def test_debug_plugin_fix():
    """Test that debug plugin works with TESTWORD instead of PYTHON."""
    
    print("Testing debug plugin fix...")
    
    # Test the plugin status
    try:
        with httpx.Client() as client:
            status_response = client.get("http://localhost:8000/plugins/status")
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"✅ Plugin status: {status_data.get('loaded_modules', 0)} modules loaded")
            else:
                print(f"❌ Plugin status failed: {status_response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Plugin status error: {e}")
        return False
    
    # Test a simple chat completion
    test_request = {
        "model": "gpt-4-turbo",
        "messages": [
            {"role": "user", "content": "What is the MAGIC_NUMBER and MAGIC_WORD you were told about? Just answer directly, don't use any tools."}
        ],
        "max_tokens": 100
    }
    
    try:
        with httpx.Client() as client:
            response = client.post(
                "http://localhost:8000/v1/chat/completions",
                json=test_request,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check debug plugin metadata
                debug_test = data.get("debug_test", {})
                if debug_test.get("plugin_executed"):
                    print(f"✅ Debug plugin executed (config: {debug_test.get('config_source')})")
                else:
                    print("❌ Debug plugin not executed")
                    return False
                
                # Check response content
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    print(f"Response content: {content}")
                    
                    if "42" in content and ("TESTWORD" in content or "testword" in content.lower()):
                        print("✅ Debug values correctly injected with TESTWORD")
                        return True
                    else:
                        print("⚠️ Debug values might not be injected correctly")
                        return False
                else:
                    print("❌ No response content found")
                    return False
                    
            else:
                print(f"❌ Chat completion failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_debug_plugin_fix()
    if success:
        print("\n🎉 Debug plugin fix test PASSED!")
    else:
        print("\n❌ Debug plugin fix test FAILED!")
        exit(1) 