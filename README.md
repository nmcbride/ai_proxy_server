# ai_proxy_server

# Environment Variables

The server can be configured using environment variables:

## Server Configuration
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: 8000)  
- `DEBUG`: Enable debug mode (default: false)

## LiteLLM Integration
- `LITELLM_BASE_URL`: LiteLLM server URL (default: "http://localhost:4000")
- `LITELLM_API_KEY`: Optional API key for LiteLLM
- `LITELLM_MASTER_KEY`: Optional master key for LiteLLM

## Tool Calling Configuration
- `MAX_TOOL_ROUNDS`: Maximum number of tool calling rounds to prevent infinite loops (default: 5)
- `TOOL_EXECUTION_TIMEOUT`: Timeout for individual tool execution in seconds (default: 30.0)
- `ENABLE_HYBRID_STREAMING`: Enable hybrid streaming mode (tool calling + streaming final response) (default: false)

## HTTP Client Configuration
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 300.0)
- `MAX_CONNECTIONS`: Maximum HTTP connections (default: 100)
- `MAX_KEEPALIVE_CONNECTIONS`: Maximum keepalive connections (default: 20)