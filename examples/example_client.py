"""
Example client for testing the AI Proxy Server
"""

import asyncio

import httpx
from openai import OpenAI

# Configure OpenAI client to use our proxy
client = OpenAI(
    api_key="test-key",  # This will be forwarded to LiteLLM
    base_url="http://localhost:8000",  # Our proxy server
)


async def test_chat_completion():
    """Test chat completion with request/response modification"""
    print("🔄 Testing Chat Completion...")

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Explain quantum computing in simple terms"}
            ],
            max_tokens=150,
        )

        print("✅ Chat Completion Response:")
        print(f"Model: {response.model}")
        print(f"Content: {response.choices[0].message.content}")

        # Check for proxy modifications
        if hasattr(response, "_proxy"):
            print(f"🔧 Proxy Info: {response._proxy}")

        return response
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def test_completion():
    """Test text completion"""
    print("\n🔄 Testing Text Completion...")

    try:
        response = client.completions.create(
            model="gpt-3.5-turbo-instruct",
            prompt="The future of artificial intelligence is",
            max_tokens=100,
        )

        print("✅ Text Completion Response:")
        print(f"Text: {response.choices[0].text}")

        return response
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def test_embeddings():
    """Test embeddings endpoint"""
    print("\n🔄 Testing Embeddings...")

    try:
        response = client.embeddings.create(
            model="text-embedding-ada-002", input="Hello, world!"
        )

        print("✅ Embeddings Response:")
        print(f"Embedding dimensions: {len(response.data[0].embedding)}")
        print(f"Usage: {response.usage}")

        return response
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def test_models_list():
    """Test models list endpoint"""
    print("\n🔄 Testing Models List...")

    try:
        response = client.models.list()

        print("✅ Models List Response:")
        print(f"Available models: {len(response.data)}")

        # Look for our custom proxy model
        proxy_models = [
            model for model in response.data if hasattr(model, "_is_proxy_model")
        ]
        if proxy_models:
            print(f"🔧 Found {len(proxy_models)} proxy-enhanced models")

        return response
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def test_with_context_injection():
    """Test request modification with context injection"""
    print("\n🔄 Testing Context Injection...")

    try:
        # This should trigger the system context injection if configured
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": "What should I know about investing?"}
            ],
            max_tokens=200,
        )

        print("✅ Context Injection Response:")
        print(f"Content: {response.choices[0].message.content}")

        # Check if disclaimer was added for financial content
        if "informational purposes only" in response.choices[0].message.content:
            print("🔧 Financial disclaimer was automatically added!")

        return response
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def test_streaming():
    """Test streaming response"""
    print("\n🔄 Testing Streaming Response...")

    try:
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Count from 1 to 5"}],
            stream=True,
        )

        print("✅ Streaming Response:")
        content = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content += chunk.choices[0].delta.content
                print(chunk.choices[0].delta.content, end="")

        print(f"\n📝 Full content: {content}")

        return content
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def test_with_custom_headers():
    """Test with custom headers for advanced features"""
    print("\n🔄 Testing Custom Headers...")

    try:
        # Using httpx directly to add custom headers
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                "http://localhost:8000/v1/chat/completions",
                headers={
                    "Authorization": "Bearer test-key",
                    "Content-Type": "application/json",
                    "X-User-ID": "test-user-123",
                    "X-Session-ID": "session-456",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Hello from custom headers test!"}
                    ],
                    "max_tokens": 100,
                },
            )

            if response.status_code == 200:
                data = response.json()
                print("✅ Custom Headers Response:")
                print(f"Content: {data['choices'][0]['message']['content']}")

                if "_proxy_info" in data:
                    print(
                        f"🔧 Proxy modifications: {data['_proxy_info']['modifications_applied']}"
                    )

                return data
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def test_health_check():
    """Test proxy health endpoint"""
    print("\n🔄 Testing Health Check...")

    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get("http://localhost:8000/health")

            if response.status_code == 200:
                data = response.json()
                print("✅ Health Check Response:")
                print(f"Status: {data['status']}")
                print(f"Timestamp: {data['timestamp']}")
                return data
            else:
                print(f"❌ Error: {response.status_code}")
                return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def main():
    """Run all tests"""
    print("🚀 AI Proxy Server Test Suite")
    print("=" * 50)

    # Test health check first
    await test_health_check()

    # Test basic endpoints
    await test_chat_completion()
    await test_completion()
    await test_embeddings()
    await test_models_list()

    # Test advanced features
    await test_with_context_injection()
    await test_streaming()
    await test_with_custom_headers()

    print("\n" + "=" * 50)
    print("✅ Test suite completed!")


if __name__ == "__main__":
    asyncio.run(main())
