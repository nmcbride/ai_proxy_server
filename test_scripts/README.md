# Test Scripts

This directory contains test scripts for the AI Proxy Server, organized by functionality and testing purpose.

## 🚀 Recommended Testing (Start Here)

### Comprehensive Test Suite
- **`test_comprehensive.py`** - **⭐ MAIN TEST SCRIPT** - Tests all modes and scenarios in one run
- **`test_all_modes.py`** - **⭐ COMPLETE VALIDATION** - Tests both direct streaming and hybrid streaming modes

### Quick Usage
```bash
# Test current server configuration (respects current ENABLE_HYBRID_STREAMING setting)
python test_scripts/test_comprehensive.py

# Test BOTH streaming modes (automatically tests direct + hybrid streaming)
python test_scripts/test_all_modes.py
```

### What Gets Tested
The comprehensive suite covers:

| Mode | Tools | Test Case | Expected Behavior |
|------|-------|-----------|-------------------|
| Non-streaming | ✅ | Debug tools query | Tool execution → Final response |
| Non-streaming | ❌ | Haiku request | Direct response (no tools) |
| Direct streaming | ❌ | Debug tools query | Skip tools → Stream response |
| Hybrid streaming | ✅ | Debug tools query | Tool execution → Stream final response |
| Hybrid streaming | ❌ | Story request | Stream response (no tools needed) |

## 🔧 Legacy/Specific Test Scripts

### Debug Scripts
- **`debug_simple.py`** - Basic debug script for simple proxy testing
- **`debug_client.py`** - Client debug script for testing proxy connections
- **`debug_direct.py`** - Direct LiteLLM testing without proxy
- **`debug_real_time.py`** - Real-time streaming test script

### Functional Test Scripts
- **`test_hybrid_streaming.py`** - Tests hybrid streaming functionality (tool calling + streaming final response)
- **`test_mcp_flow.py`** - Comprehensive MCP (Model Context Protocol) flow testing
- **`test_minimal_proxy.py`** - Minimal proxy functionality test

### Shell Scripts
- **`test_litellm_direct.sh`** - Shell script for testing direct LiteLLM connections
- **`test_proxy_streaming.sh`** - Shell script for testing proxy streaming functionality
- **`test_streaming_comparison.sh`** - Compares streaming performance between direct LiteLLM and proxy

## 📋 Usage Instructions

### Running Comprehensive Tests
```bash
# From project root - test current configuration
uv run python test_scripts/test_comprehensive.py

# Test both streaming modes (recommended for full validation)
uv run python test_scripts/test_all_modes.py
```

### Running Legacy/Specific Tests
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

## 🔍 Understanding Streaming Modes

### Direct Streaming (`ENABLE_HYBRID_STREAMING=false`)
- Streaming requests skip tool calling entirely
- Fast response times
- No tool integration
- Good for pure content generation

### Hybrid Streaming (`ENABLE_HYBRID_STREAMING=true`) 
- Streaming requests can use tools first, then stream final response
- Tool execution + streaming final response
- Longer initial delay but streaming final answer
- Best of both worlds: tool capabilities + streaming UX

## Prerequisites

- AI Proxy Server running on port 8001
- LiteLLM server running on port 4000  
- MCP servers configured and running
- Valid API keys configured

## Test Categories

### Performance Tests
- `test_streaming_comparison.sh` - Streaming performance
- `debug_real_time.py` - Real-time response timing
- **`test_comprehensive.py`** - Performance comparison across all modes

### Functionality Tests  
- **`test_comprehensive.py`** - All modes and tool scenarios
- **`test_all_modes.py`** - Both streaming mode validation
- `test_hybrid_streaming.py` - Hybrid streaming mode
- `test_mcp_flow.py` - Tool calling workflows
- `test_minimal_proxy.py` - Basic proxy functions

### Debug/Development
- `debug_simple.py` - Quick debugging
- `debug_client.py` - Client-side debugging  
- `debug_direct.py` - LiteLLM direct testing

## Environment Variables

Key environment variables for testing:
```bash
export ENABLE_HYBRID_STREAMING=true   # Enable hybrid streaming mode
export MAX_TOOL_ROUNDS=5             # Max tool calling rounds
export TOOL_EXECUTION_TIMEOUT=30.0   # Tool execution timeout
export LITELLM_BASE_URL=http://localhost:4000
export PROXY_BASE_URL=http://localhost:8001
```

The `test_all_modes.py` script automatically tests both `ENABLE_HYBRID_STREAMING=true` and `ENABLE_HYBRID_STREAMING=false` modes. 