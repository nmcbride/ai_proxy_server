# MCP Servers

This directory contains custom MCP (Model Context Protocol) servers that are shipped with the AI Proxy Server.

## Available Servers

### `debug_server.py`
A debug/testing MCP server with predictable outputs for verifying tool calling functionality.

**Tools provided:**
- `get_debug_number` - Returns a fixed number (42) for testing
- `get_timestamp` - Returns current timestamp for freshness verification  
- `get_call_counter` - Returns incrementing counter for multi-call testing
- `echo_message` - Echoes back provided message for parameter testing
- `debug_math` - Performs simple math operations for complex parameter testing

**Usage:**
```bash
# Test basic tool calling
"Call the get_debug_number tool" → Returns "DEBUG_NUMBER: 42"

# Test with parameters
"Echo the message 'hello world'" → Returns "ECHO: hello world"

# Test math operations
"Calculate 10 * 5 using debug_math" → Returns "MATH_RESULT: 10.0 multiply 5.0 = 50.0"
```

## Configuration

These servers are configured in `config/mcp_servers.yaml`:

```yaml
mcp_servers:
  debug:
    transport: stdio
    command: uv
    args: ["run", "python", "mcp_servers/debug_server.py"]
    description: "Debug tools for testing MCP integration"
```

## Adding New Servers

1. Create your MCP server in this directory
2. Add configuration to `config/mcp_servers.yaml`
3. Restart the proxy server to load the new server
4. Test with both streaming and non-streaming requests

## Examples vs MCP Servers

- **`examples/`** - Demo servers for learning and reference
- **`mcp_servers/`** - Production-ready servers shipped with the product 