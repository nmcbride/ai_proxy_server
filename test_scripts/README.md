# AI Proxy Server - Test Suite

This directory contains all test scripts for validating the AI proxy server functionality.

## Test Scripts

### Core Functionality Tests

#### `test_proxy_streaming.py` **RECOMMENDED STARTING POINT**
**Purpose**: Modern Python test suite for core proxy functionality
- Health check validation
- Non-streaming chat completions
- Streaming chat completions with metrics
- CORS header validation
- Beautiful console output with performance metrics

**Usage**:
```bash
cd test_scripts
uv run python test_proxy_streaming.py
```

#### `test_comprehensive.py`
**Purpose**: Advanced test suite for all server modes and configurations
- Tests hybrid streaming vs direct streaming modes
- Validates MCP tool integration
- Performance benchmarking across different modes
- Error handling verification

**Usage**:
```bash
cd test_scripts
uv run python test_comprehensive.py
```

#### `test_mcp_flow.py`
**Purpose**: Specialized testing for MCP (Model Context Protocol) tool calling
- Tests tool detection and execution
- Validates tool call responses
- MCP server connection testing

**Usage**:
```bash
cd test_scripts
uv run python test_mcp_flow.py
```

### Web Client Tests

#### `test_web_client.html`
**Purpose**: Interactive browser-based testing for web client compatibility
- Interactive streaming tests
- Non-streaming tests
- CORS validation from browsers
- Visual feedback and real-time metrics
- Click-to-test interface

**Usage**:
1. Ensure proxy server is running on `localhost:8001`
2. Open `test_scripts/test_web_client.html` in a web browser
3. Click test buttons to validate functionality

### Profiling & Performance

#### `profiling_dashboard.html`
**Purpose**: Real-time profiling dashboard for request performance analysis
- Live request monitoring with auto-refresh
- Expandable timeline views for each request
- Phase-by-phase timing breakdown
- Request metadata (tool counts, data sizes)
- Bottleneck identification

**Features**:
- Visual timeline bars showing relative phase durations
- Request cards with total time and phase counts
- Status indicators and system health monitoring
- Export capabilities for detailed analysis

**Usage**:
1. Ensure proxy server is running on `localhost:8000`
2. Open `test_scripts/profiling_dashboard.html` in a web browser
3. Dashboard auto-refreshes every 5 seconds
4. Click request cards to expand detailed timelines

#### `test_profiling_dashboard.py`
**Purpose**: Test script to generate profiling data and open dashboard
- Automatically starts server if needed
- Makes diverse test requests (streaming, tools, hybrid)
- Opens dashboard in default browser
- Validates profiling system functionality

**Usage**:
```bash
cd test_scripts
uv run python test_profiling_dashboard.py
```

## Quick Testing Guide

### 1. Start Here - Basic Functionality
```bash
cd test_scripts
uv run python test_proxy_streaming.py
```
**Expected**: All 4 tests pass (Health, Non-Streaming, Streaming, CORS)

### 2. Web Browser Compatibility
```bash
# Open in browser (requires running server)
open test_scripts/test_web_client.html
```
**Expected**: Both streaming and non-streaming tests work in browser

### 3. MCP Tool Integration
```bash
cd test_scripts
uv run python test_mcp_flow.py
```
**Expected**: Tool calling and execution work properly

### 4. Profiling & Performance Analysis **NEW**
```bash
cd test_scripts
uv run python test_profiling_dashboard.py
```
**Expected**: Dashboard opens showing real-time request profiling data

### 5. Advanced/Complete Testing
```bash
cd test_scripts
uv run python test_comprehensive.py
```
**Expected**: All modes and configurations work correctly

## File Overview

| File | Purpose | Type | Complexity |
|------|---------|------|------------|
| `test_proxy_streaming.py` | Main testing | Python | Simple |
| `test_web_client.html` | Browser testing | HTML/JS | Simple |
| `profiling_dashboard.html` | Performance dashboard | HTML/JS | Simple |
| `test_profiling_dashboard.py` | Profiling test | Python | Simple |
| `test_comprehensive.py` | Advanced testing | Python | Complex |
| `test_mcp_flow.py` | Tool calling | Python | Medium |
| `README.md` | Documentation | Markdown | - |

## Test Requirements

- AI proxy server running on `localhost:8001`
- Valid OpenAI API key configured in the proxy
- Python dependencies: `httpx`, `asyncio` (handled by uv)
- For MCP tests: MCP servers configured in `configs/mcp_servers.yaml`
- For web tests: Modern web browser with JavaScript enabled

## Expected Results

**All tests should pass** when:
- Proxy server is properly configured and running
- OpenAI API key is valid and has quota
- MCP servers are running (for MCP-specific tests)
- CORS headers are properly configured

**Tests may fail** due to:
- Network connectivity issues
- Invalid or exhausted API key
- Proxy server not running on expected port
- MCP server connection problems
- CORS policy restrictions (web tests only)

## Troubleshooting

**Server not reachable**: Ensure server is running on port 8001
```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**API errors**: Check your OpenAI API key configuration

**CORS issues**: Ensure CORS headers are enabled (should work automatically)

**MCP errors**: Check that MCP servers are configured and running 