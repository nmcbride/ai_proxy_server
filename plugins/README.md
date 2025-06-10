# AI Proxy Server Plugin System

The AI Proxy Server includes a flexible plugin system that allows you to extend functionality without modifying core code. Plugins can modify requests before they're sent to the upstream LLM and responses before they're returned to clients.

## How Plugins Work

Plugins operate using two main hooks:

1. **`before_request`**: Modify requests before they're sent to the upstream LLM
2. **`after_request`**: Modify responses before they're returned to clients

Plugins are processed in the order they're loaded, and each plugin receives the output of the previous plugin.

## Core vs Plugin Functionality

**Important**: The plugin system is designed for optional enhancements only. Core functionality like MCP tool integration remains in the core system and cannot be disabled by accident.

- **Core functionality** (always enabled): MCP tool calling, basic proxy operations, authentication
- **Plugin functionality** (optional): System context injection, metadata enhancement, temperature control, custom modifications

## Creating Custom Plugins

### 1. Plugin Structure

Create a Python file in the `plugins/user/` directory:

```python
from typing import Any, Dict, List
from app.plugin_system.base_plugin import BasePlugin

class MyCustomPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "my_custom_plugin"
    
    @property
    def description(self) -> str:
        return "Description of what this plugin does"
    
    @property
    def endpoints(self) -> List[str]:
        # Specify which endpoints this plugin should handle
        return ["/v1/chat/completions"]  # or ["*"] for all endpoints
    
    async def before_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        # Modify the request here
        return request_data
    
    async def after_request(self, response_data: Dict[str, Any], request_data: Dict[str, Any]) -> Dict[str, Any]:
        # Modify the response here
        return response_data
```

### 2. Endpoint Targeting

You can specify which endpoints your plugin should handle:

```python
@property
def endpoints(self) -> List[str]:
    return [
        "/v1/chat/completions",      # Exact path
        "/v1/completions",           # Exact path
        "*"                          # All endpoints
    ]
```

### 3. Configuration

Configure your plugin in `config/plugins.yaml`:

```yaml
plugins:
  mycustomplugin:  # Plugin name (lowercase, no underscores)
    enabled: true
    config:
      my_setting: "value"
      another_setting: 42
```

Access configuration in your plugin:

```python
async def before_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    my_setting = self.config.get("my_setting", "default_value")
    # Use the setting...
    return request_data
```

## Built-in Plugins

### System Context Plugin
- **Purpose**: Injects system context into chat requests that don't have a system message
- **Endpoints**: `/v1/chat/completions`
- **Configuration**: Set custom context text

### Metadata Enhancer Plugin
- **Purpose**: Adds metadata to responses (timestamps, version info, etc.)
- **Endpoints**: All endpoints
- **Configuration**: Control what metadata to add

### Temperature Control Plugin
- **Purpose**: Controls and limits temperature parameters
- **Endpoints**: `/v1/chat/completions`, `/v1/completions`
- **Configuration**: Set min/max limits and defaults

## Plugin Configuration

Edit `config/plugins.yaml` to control plugins:

```yaml
plugins:
  # System Context Plugin
  systemcontext:
    enabled: true
    config:
      context: "You are a helpful AI assistant."
  
  # Metadata Enhancer Plugin  
  metadataenhancer:
    enabled: true
    config:
      add_timestamp: true
      add_version: true
  
  # Temperature Control Plugin
  temperaturecontrol:
    enabled: true
    config:
      min_temperature: 0.0
      max_temperature: 2.0
  
  # Custom user plugin
  mycustomplugin:
    enabled: false  # Disabled by default
    config:
      custom_setting: "value"
```

## Plugin Status

Check plugin status via the API:

```bash
curl http://localhost:8001/plugins/status
```

This returns information about loaded plugins:

```json
{
  "total_plugins": 3,
  "enabled_plugins": 3,
  "plugins": [
    {
      "name": "system_context",
      "description": "Injects system context into chat completion requests",
      "version": "1.0.0",
      "enabled": true,
      "endpoints": ["/v1/chat/completions"]
    }
  ]
}
```

## Best Practices

1. **Keep plugins focused**: Each plugin should have a single, clear purpose
2. **Handle errors gracefully**: Plugin errors are logged but don't break the request
3. **Use configuration**: Make plugins configurable rather than hardcoding values
4. **Document your plugins**: Include clear descriptions and examples
5. **Test thoroughly**: Test plugins with various request types and edge cases

## Debugging Plugins

Plugin errors are logged with structured logging. Check server logs for messages like:

```
Plugin before_request failed plugin=my_plugin error=...
Plugin after_request failed plugin=my_plugin error=...
```

You can also add logging to your plugins:

```python
import structlog

logger = structlog.get_logger()

async def before_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Plugin processing request", plugin=self.name)
    # ... plugin logic
    return request_data
``` 