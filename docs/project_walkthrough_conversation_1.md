# Step by step project walkthrough
_Exported on 6/8/2025 at 23:06:08 EDT from Cursor (1.0.0)_

---

**User**

can you walk me through this project step by step and tell me how everything works and is implemented

---

**Cursor**

I'll walk you through this AI proxy server project step by step. Let me first explore the codebase structure to understand all the components.

Now let me read the key configuration and component files to understand how everything fits together:

Now let me look at some of the test and debug files to better understand how the system works:

Now I have a comprehensive understanding of the project. Let me walk you through this AI Proxy Server step by step:

## **AI Proxy Server: Complete Project Walkthrough**

This is a **FastAPI-based proxy server** that sits between clients and a LiteLLM upstream server, providing request/response modification capabilities for OpenAI-compatible API endpoints.

### **🏗️ Architecture Overview**

```
Client (OpenAI SDK) → AI Proxy Server (FastAPI) → LiteLLM Server → Various AI Models
```

The system consists of two main services:
1. **LiteLLM Server** (upstream): Handles multiple AI model providers
2. **AI Proxy Server** (this project): Intercepts and modifies requests/responses

---

## **📁 Project Structure**

### **Core Application (`app/`)**
- **`main.py`** - FastAPI application with all endpoints and proxy logic
- **`config.py`** - Settings management using Pydantic
- **`middleware.py`** - Custom middleware for logging and proxy functionality
- **`request_modifiers.py`** - Classes to modify requests before sending upstream
- **`response_modifiers.py`** - Classes to modify responses before returning to client
- **`utils.py`** - Helper functions (request ID generation, IP extraction, etc.)
- **`models.py`** - Pydantic models for data validation

### **Configuration & Deployment**
- **`litellm_config.yaml`** - LiteLLM server configuration
- **`docker-compose.yml`** - Container orchestration
- **`Dockerfile`** - Container build instructions
- **`pyproject.toml`** - Python project configuration and dependencies

### **Testing & Examples**
- **`examples/`** - Client usage examples
- **`debug_*.py`** - Various debugging scripts
- **`test_*.py`** & **`test_*.sh`** - Test scripts

---

## **⚙️ How It Works**

### **1. Configuration System (`app/config.py`)**

The application uses **Pydantic Settings** for configuration management:

```python
class Settings(BaseSettings):
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # LiteLLM upstream
    LITELLM_BASE_URL: str = "http://localhost:4000"
    LITELLM_API_KEY: str = ""
    
    # Feature flags
    ENABLE_REQUEST_MODIFICATION: bool = True
    ENABLE_RESPONSE_MODIFICATION: bool = True
```

**Key Features:**
- Environment variable support (`.env` file)
- Type validation
- Default values
- Configurable timeouts, connection limits, CORS, etc.

### **2. Application Lifecycle (`app/main.py`)**

The FastAPI app uses an **async context manager** for startup/shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize HTTP client
    global http_client
    http_client = httpx.AsyncClient(...)
    
    yield
    
    # Shutdown: Clean up resources
    await http_client.aclose()
```

### **3. Middleware Stack (`app/middleware.py`)**

Two custom middleware classes:

**a) LoggingMiddleware:**
- Generates unique request IDs
- Logs request/response details with structured logging
- Measures processing time
- Adds request ID to response headers

**b) ProxyMiddleware:**
- Adds proxy-specific headers
- Tracks proxy version and timestamp

### **4. Core Proxy Logic (`proxy_request` function)**

This is the heart of the system. Here's how it works:

#### **Step 1: Request Preparation**
```python
# Generate unique ID for tracking
proxy_request_id = generate_request_id()

# Get request body and parse JSON
body = await request.body()
request_data = json.loads(body)

# Check if streaming is requested
is_streaming_request = request_data.get("stream", False)
```

#### **Step 2: Request Modification**
```python
if modify_request:
    modified_data = await request_modifier.modify_request(
        path, request_data, request
    )
    body = json.dumps(modified_data).encode()
```

#### **Step 3: Upstream Request**
```python
# Prepare upstream URL and headers
upstream_url = f"{settings.LITELLM_BASE_URL.rstrip('/')}{path}"

# Forward request to LiteLLM
upstream_response = await client.request(
    method=method,
    url=upstream_url,
    headers=headers,
    content=body,
    stream=is_streaming_request
)
```

#### **Step 4: Response Handling**

**For Streaming Responses:**
```python
async def stream_generator():
    async for line in upstream_response.aiter_lines():
        if line.strip():
            yield (line + "\n").encode()

return StreamingResponse(stream_generator(), ...)
```

**For Regular Responses:**
```python
# Modify response if enabled
if modify_response:
    response_data = json.loads(response_content)
    modified_data = await response_modifier.modify_response(...)
    response_content = json.dumps(modified_data).encode()
```

### **5. Request Modification System (`app/request_modifiers.py`)**

The `RequestModifier` class provides extensible request transformation:

#### **Chat Completions Modifications:**
- **System context injection:** Adds system prompts if missing
- **User identification:** Tracks client IP in messages
- **Model-specific settings:** Auto-adjusts temperature for GPT-4
- **Default parameters:** Sets max_tokens, response format

#### **Text Completions Modifications:**
- **Context prefixing:** Prepends system context to prompts
- **Parameter normalization:** Sets default temperature, max_tokens

#### **Embeddings Modifications:**
- **Text preprocessing:** Cleans and normalizes input text
- **Model defaults:** Sets default embedding model

**Example System Context Injection:**
```python
if settings.SYSTEM_CONTEXT and "messages" in request_data:
    messages = request_data["messages"]
    
    # Add system message if none exists
    if not any(msg.get("role") == "system" for msg in messages):
        system_message = {"role": "system", "content": settings.SYSTEM_CONTEXT}
        request_data["messages"] = [system_message] + messages
```

### **6. Response Modification System (`app/response_modifiers.py`)**

The `ResponseModifier` class transforms responses before returning to client:

#### **Chat Completions Modifications:**
- **Proxy metadata:** Adds processing info, timing, version
- **Content post-processing:** Applies formatting, safety filters
- **Usage enhancement:** Adds proxy-specific usage metrics
- **Safety filtering:** Content moderation capabilities

#### **Models List Modifications:**
- **Custom models:** Adds proxy-enhanced model variants
- **Feature advertising:** Shows what proxy features are available

**Example Response Enhancement:**
```python
# Add proxy metadata
response_data["_proxy_info"] = {
    "original_model": original_model,
    "proxy_timestamp": int(time.time()),
    "modifications_applied": [
        "content_processing",
        "safety_filters", 
        "metadata_addition"
    ]
}
```

### **7. API Endpoints**

The proxy implements **all major OpenAI v1 endpoints:**

- **`/v1/chat/completions`** - Chat completions (with and without `/v1` prefix)
- **`/v1/completions`** - Text completions  
- **`/v1/embeddings`** - Text embeddings
- **`/v1/models`** - Model listing
- **`/v1/moderations`** - Content moderation
- **`/v1/images/generations`** - Image generation
- **`/v1/audio/*`** - Audio endpoints (speech, transcriptions, translations)
- **`/v1/{path:path}`** - Catch-all for other endpoints
- **`/health`** - Health check

Each endpoint uses the same `proxy_request()` function with different paths.

### **8. LiteLLM Upstream Configuration**

The `litellm_config.yaml` configures the upstream server:

```yaml
model_list:
  - model_name: gpt-4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY
      
  - model_name: text-embedding-ada-002
    litellm_params:
      model: openai/text-embedding-ada-002
      api_key: os.environ/OPENAI_API_KEY
```

**Features:**
- **Multi-provider support:** OpenAI, Anthropic, Google, Azure, etc.
- **Environment variable integration:** Secure API key management
- **Load balancing:** Optional routing strategies
- **Logging and callbacks:** Integration with monitoring tools

### **9. Docker Deployment**

The `docker-compose.yml` orchestrates the full stack:

```yaml
services:
  litellm:          # Upstream LiteLLM server
    image: ghcr.io/berriai/litellm:main-latest
    ports: ["4000:4000"]
    
  # ai-proxy:       # Our FastAPI proxy (commented out)
  #   build: .
  #   ports: ["8000:8000"]
    
  redis:            # Optional caching layer
    image: redis:7-alpine
```

---

## **🔄 Request Flow Example**

Let's trace a chat completion request:

### **1. Client Request**
```python
client = OpenAI(base_url="http://localhost:8000")
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### **2. Proxy Processing**
1. **LoggingMiddleware** generates request ID, starts timing
2. **ProxyMiddleware** adds proxy headers
3. **Route matching** to `/v1/chat/completions` endpoint
4. **Request modification:**
   - Parses JSON body
   - Injects system context if configured
   - Adds client IP tracking
   - Sets default parameters

### **3. Upstream Request**
```python
# Modified request sent to LiteLLM
{
    "model": "gpt-3.5-turbo",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!\n\n[Request from: 192.168.1.100]"}
    ],
    "max_tokens": 2048,
    "temperature": 0.3
}
```

### **4. Response Processing**
1. **LiteLLM** processes request, returns response
2. **Response modification:**
   - Adds proxy metadata
   - Applies content filters
   - Enhances usage statistics
   - Adds processing timestamps

### **5. Client Response**
```python
{
    "choices": [{"message": {"content": "Hello! How can I help you today?"}}],
    "usage": {"total_tokens": 25, "proxy_processing_time": 0.1},
    "_proxy_info": {
        "modifications_applied": ["content_processing", "safety_filters"],
        "proxy_timestamp": 1699123456
    }
}
```

---

## **🚀 Key Features & Benefits**

### **Request/Response Transformation**
- **System prompt injection**
- **Content filtering and safety**
- **Parameter normalization**  
- **User identification and tracking**

### **Monitoring & Observability**
- **Structured logging** with request tracing
- **Performance metrics** and timing
- **Request/response modification tracking**
- **Error handling and debugging**

### **Extensibility**
- **Modular design** for easy customization
- **Advanced modifier classes** for complex logic
- **Plugin-ready architecture**
- **Configuration-driven behavior**

### **Production Ready**
- **Async/await** throughout for performance
- **Connection pooling** and timeouts
- **Health checks** and graceful shutdown
- **CORS support** and security headers
- **Docker deployment** with orchestration

---

## **💡 Use Cases**

This proxy server enables powerful AI application patterns:

1. **Content Moderation:** Filter harmful content automatically
2. **Context Injection:** Add company-specific instructions  
3. **Usage Tracking:** Monitor and analyze AI usage patterns
4. **Cost Optimization:** Route to cheaper models when appropriate
5. **A/B Testing:** Experiment with different prompting strategies
6. **Compliance:** Add legal disclaimers or audit trails
7. **Personalization:** Customize responses based on user data

The modular architecture makes it easy to add custom business logic while maintaining compatibility with existing OpenAI SDK clients.

```plaintext
Client (OpenAI SDK) → AI Proxy Server (FastAPI) → LiteLLM Server → Various AI Models
```

```python
class Settings(BaseSettings):
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # LiteLLM upstream
    LITELLM_BASE_URL: str = "http://localhost:4000"
    LITELLM_API_KEY: str = ""
    
    # Feature flags
    ENABLE_REQUEST_MODIFICATION: bool = True
    ENABLE_RESPONSE_MODIFICATION: bool = True
```

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize HTTP client
    global http_client
    http_client = httpx.AsyncClient(...)
    
    yield
    
    # Shutdown: Clean up resources
    await http_client.aclose()
```

```python
# Generate unique ID for tracking
proxy_request_id = generate_request_id()

# Get request body and parse JSON
body = await request.body()
request_data = json.loads(body)

# Check if streaming is requested
is_streaming_request = request_data.get("stream", False)
```

```python
if modify_request:
    modified_data = await request_modifier.modify_request(
        path, request_data, request
    )
    body = json.dumps(modified_data).encode()
```

```python
# Prepare upstream URL and headers
upstream_url = f"{settings.LITELLM_BASE_URL.rstrip('/')}{path}"

# Forward request to LiteLLM
upstream_response = await client.request(
    method=method,
    url=upstream_url,
    headers=headers,
    content=body,
    stream=is_streaming_request
)
```

```python
async def stream_generator():
    async for line in upstream_response.aiter_lines():
        if line.strip():
            yield (line + "\n").encode()

return StreamingResponse(stream_generator(), ...)
```

```python
# Modify response if enabled
if modify_response:
    response_data = json.loads(response_content)
    modified_data = await response_modifier.modify_response(...)
    response_content = json.dumps(modified_data).encode()
```

```python
if settings.SYSTEM_CONTEXT and "messages" in request_data:
    messages = request_data["messages"]
    
    # Add system message if none exists
    if not any(msg.get("role") == "system" for msg in messages):
        system_message = {"role": "system", "content": settings.SYSTEM_CONTEXT}
        request_data["messages"] = [system_message] + messages
```

```python
# Add proxy metadata
response_data["_proxy_info"] = {
    "original_model": original_model,
    "proxy_timestamp": int(time.time()),
    "modifications_applied": [
        "content_processing",
        "safety_filters", 
        "metadata_addition"
    ]
}
```

```yaml
model_list:
  - model_name: gpt-4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY
      
  - model_name: text-embedding-ada-002
    litellm_params:
      model: openai/text-embedding-ada-002
      api_key: os.environ/OPENAI_API_KEY
```

```yaml
services:
  litellm:          # Upstream LiteLLM server
    image: ghcr.io/berriai/litellm:main-latest
    ports: ["4000:4000"]
    
  # ai-proxy:       # Our FastAPI proxy (commented out)
  #   build: .
  #   ports: ["8000:8000"]
    
  redis:            # Optional caching layer
    image: redis:7-alpine
```

```python
client = OpenAI(base_url="http://localhost:8000")
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

```python
# Modified request sent to LiteLLM
{
    "model": "gpt-3.5-turbo",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!\n\n[Request from: 192.168.1.100]"}
    ],
    "max_tokens": 2048,
    "temperature": 0.3
}
```

```python
{
    "choices": [{"message": {"content": "Hello! How can I help you today?"}}],
    "usage": {"total_tokens": 25, "proxy_processing_time": 0.1},
    "_proxy_info": {
        "modifications_applied": ["content_processing", "safety_filters"],
        "proxy_timestamp": 1699123456
    }
}
```

