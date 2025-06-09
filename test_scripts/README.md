# Test Scripts

This directory contains various test scripts for the AI Proxy Server, organized by functionality and testing purpose.

## Debug Scripts

### `debug_simple.py`
Basic debug script for simple proxy testing.

### `debug_client.py` 
Client debug script for testing proxy connections.

### `debug_direct.py`
Direct LiteLLM testing without proxy.

### `debug_real_time.py`
Real-time streaming test script.

## Functional Test Scripts

### `test_hybrid_streaming.py`
Tests the hybrid streaming functionality (tool calling + streaming final response).
- Tests both streaming and non-streaming requests
- Verifies tool calling integration
- Measures timing and performance

### `test_mcp_flow.py`
Comprehensive MCP (Model Context Protocol) flow testing.
- Tests tool calling workflows
- Verifies MCP server integration
- Tests multiple rounds of tool calls

### `test_minimal_proxy.py`
Minimal proxy functionality test.
- Basic proxy forwarding
- Simple request/response verification

## Shell Scripts

### `test_litellm_direct.sh`
Shell script for testing direct LiteLLM connections.

### `test_proxy_streaming.sh`
Shell script for testing proxy streaming functionality.

### `test_streaming_comparison.sh`
Compares streaming performance between direct LiteLLM and proxy.

## Usage

### Running Python Tests
```bash
# From project root
uv run python test_scripts/test_hybrid_streaming.py
uv run python test_scripts/test_mcp_flow.py
uv run python test_scripts/debug_client.py
```

### Running Shell Scripts
```bash
# From project root
chmod +x test_scripts/*.sh
./test_scripts/test_streaming_comparison.sh
./test_scripts/test_proxy_streaming.sh
```

## Prerequisites

- AI Proxy Server running on port 8001
- LiteLLM server running on port 4000
- MCP servers configured and running
- Valid API keys configured

## Test Categories

### Performance Tests
- `test_streaming_comparison.sh` - Streaming performance
- `debug_real_time.py` - Real-time response timing

### Functionality Tests  
- `test_hybrid_streaming.py` - Hybrid streaming mode
- `test_mcp_flow.py` - Tool calling workflows
- `test_minimal_proxy.py` - Basic proxy functions

### Debug/Development
- `debug_simple.py` - Quick debugging
- `debug_client.py` - Client-side debugging  
- `debug_direct.py` - LiteLLM direct testing

## Environment Variables

Some tests may require environment variables:
```bash
export ENABLE_HYBRID_STREAMING=true  # For hybrid streaming tests
export LITELLM_BASE_URL=http://localhost:4000
export PROXY_BASE_URL=http://localhost:8001
``` 