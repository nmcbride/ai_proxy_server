import httpx
from openai import OpenAI

print("🔍 Testing with httpx first...")
try:
    response = httpx.get("http://localhost:8000/v1/models", headers={"Authorization": "Bearer test-key"})
    print(f"✅ httpx success: {response.status_code}")
    print(f"📝 Response length: {len(response.text)}")
except Exception as e:
    print(f"❌ httpx error: {e}")

print("\n🔍 Testing with OpenAI client...")
try:
    client = OpenAI(
        api_key="test-key",
        base_url="http://localhost:8000",
    )
    print("🎯 Client created successfully")
    
    # Enable debug logging to see requests
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    models = client.models.list()
    print(f"✅ OpenAI client success: {len(models.data)} models")
    
except Exception as e:
    print(f"❌ OpenAI client error: {e}")
    print(f"🔧 Error type: {type(e)}")
    if hasattr(e, 'response'):
        print(f"📄 Response: {e.response}") 