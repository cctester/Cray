# Plugin Development Guide

This guide explains how to create custom plugins for Cray.

## Overview

Plugins extend Cray's functionality by providing reusable actions. Each plugin can define multiple actions that can be used in workflows.

## Plugin Structure

```python
from cray.plugins import Plugin

class MyPlugin(Plugin):
    """Plugin description."""
    
    name = "my-plugin"
    description = "What this plugin does"
    
    async def execute(
        self, 
        action: str, 
        params: dict,
        context: dict
    ) -> dict:
        """Execute an action."""
        # Implementation
        pass
```

## Required Components

### 1. Plugin Class

Inherit from `cray.plugins.Plugin`:

```python
from cray.plugins import Plugin

class MyPlugin(Plugin):
    name = "my-plugin"
    description = "My custom plugin"
```

### 2. Execute Method

The `execute` method handles all actions:

```python
async def execute(
    self,
    action: str,        # Action name
    params: dict,       # Action parameters
    context: dict       # Execution context
) -> dict:
    """Execute an action."""
    
    actions = {
        "action1": self._action1,
        "action2": self._action2,
    }
    
    if action not in actions:
        raise ValueError(f"Unknown action: {action}")
    
    return await actions[action](params)
```

### 3. Action Methods

Each action is a separate method:

```python
async def _action1(self, params: dict) -> dict:
    """Execute action1."""
    
    # Get parameters
    required_param = params.get("required_param")
    optional_param = params.get("optional_param", "default")
    
    if not required_param:
        raise ValueError("Missing required parameter: required_param")
    
    # Do work
    result = do_something(required_param, optional_param)
    
    # Return result
    return {
        "success": True,
        "result": result,
    }
```

## Parameter Handling

### Required Parameters

```python
def _action(self, params: dict) -> dict:
    # Check required parameters
    url = params.get("url")
    if not url:
        raise ValueError("Missing required parameter: url")
```

### Optional Parameters with Defaults

```python
def _action(self, params: dict) -> dict:
    # Optional with default
    timeout = params.get("timeout", 30)
    headers = params.get("headers", {})
```

### Type Validation

```python
def _action(self, params: dict) -> dict:
    items = params.get("items", [])
    
    if not isinstance(items, list):
        raise ValueError("items must be a list")
```

## Return Values

### Success Response

```python
return {
    "success": True,
    "data": result,
    "count": len(result),
}
```

### Error Response

```python
return {
    "success": False,
    "error": str(e),
}
```

## Context Access

The `context` parameter provides workflow information:

```python
async def execute(self, action: str, params: dict, context: dict) -> dict:
    # Workflow info
    workflow_id = context.get("workflow_id")
    workflow_name = context.get("workflow_name")
    
    # Previous step results
    steps = context.get("steps", {})
    previous_result = steps.get("previous_step_name")
    
    # Input variables
    input_data = context.get("input", {})
```

## Logging

Use loguru for logging:

```python
from loguru import logger

class MyPlugin(Plugin):
    async def _action(self, params: dict) -> dict:
        logger.debug(f"Executing action with params: {params}")
        logger.info("Action started")
        logger.warning("Something might be wrong")
        logger.error("Action failed")
```

## Async Operations

Plugins support async operations:

```python
import aiohttp

class HttpPlugin(Plugin):
    async def _get(self, params: dict) -> dict:
        url = params.get("url")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                body = await response.text()
                
        return {
            "status": response.status,
            "body": body,
        }
```

## File Structure

```
my_plugin/
├── __init__.py      # Plugin exports
├── plugin.py        # Plugin implementation
└── utils.py         # Helper functions
```

### `__init__.py`

```python
from .plugin import MyPlugin

__all__ = ["MyPlugin"]
```

### `plugin.py`

```python
from cray.plugins import Plugin

class MyPlugin(Plugin):
    name = "my-plugin"
    description = "My plugin"
    
    async def execute(self, action, params, context):
        # Implementation
        pass
```

## Registering Plugins

### Built-in Plugins

Add to `cray/plugins/builtin/__init__.py`:

```python
from cray.plugins.builtin.my_plugin import MyPlugin

__all__ = ["MyPlugin", ...]
```

Update `cray/plugins/__init__.py`:

```python
def _load_builtin_plugins(self):
    from cray.plugins.builtin import MyPlugin
    self.register(MyPlugin())
```

### External Plugins

Install via pip and register:

```python
from my_plugin import MyPlugin

# In your application
registry.register(MyPlugin())
```

## Testing

### Unit Tests

```python
import pytest
from cray.plugins.builtin.my_plugin import MyPlugin

@pytest.fixture
def plugin():
    return MyPlugin()

@pytest.mark.asyncio
async def test_action1(plugin):
    result = await plugin.execute("action1", {"param": "value"}, {})
    assert result["success"] == True
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_workflow_with_plugin():
    workflow = Workflow.from_yaml("test-workflow.yaml")
    result = await workflow.run()
    assert result["success"] == True
```

## Best Practices

1. **Validate inputs early** - Check required parameters at the start
2. **Return consistent structure** - Always include `success` field
3. **Handle errors gracefully** - Return error info, don't raise
4. **Log appropriately** - Debug for details, info for progress
5. **Document actions** - Add docstrings to action methods
6. **Keep actions focused** - One responsibility per action
7. **Support cancellation** - Check for cancellation in long operations

## Example: Complete Plugin

```python
"""
Weather plugin - get weather information.
"""

import aiohttp
from typing import Dict, Any
from loguru import logger

from cray.plugins import Plugin


class WeatherPlugin(Plugin):
    """Plugin for getting weather information."""
    
    name = "weather"
    description = "Get current weather and forecasts"
    
    async def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a weather action."""
        
        actions = {
            "current": self._get_current,
            "forecast": self._get_forecast,
        }
        
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        
        return await actions[action](params)
    
    async def _get_current(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get current weather for a location."""
        
        location = params.get("location")
        if not location:
            raise ValueError("Missing required parameter: location")
        
        units = params.get("units", "metric")
        
        logger.info(f"Getting weather for: {location}")
        
        try:
            # Use wttr.in (no API key needed)
            url = f"https://wttr.in/{location}?format=j1"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": f"API returned {response.status}",
                        }
                    
                    data = await response.json()
            
            current = data["current_condition"][0]
            
            return {
                "success": True,
                "location": location,
                "temperature": current["temp_C"],
                "description": current["weatherDesc"][0]["value"],
                "humidity": current["humidity"],
                "wind_speed": current["windspeedKmph"],
            }
            
        except Exception as e:
            logger.error(f"Failed to get weather: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _get_forecast(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather forecast for a location."""
        
        location = params.get("location")
        days = params.get("days", 3)
        
        if not location:
            raise ValueError("Missing required parameter: location")
        
        logger.info(f"Getting {days}-day forecast for: {location}")
        
        try:
            url = f"https://wttr.in/{location}?format=j1"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()
            
            forecast = []
            for day in data["weather"][:days]:
                forecast.append({
                    "date": day["date"],
                    "max_temp": day["maxtempC"],
                    "min_temp": day["mintempC"],
                    "description": day["hourly"][4]["weatherDesc"][0]["value"],
                })
            
            return {
                "success": True,
                "location": location,
                "forecast": forecast,
            }
            
        except Exception as e:
            logger.error(f"Failed to get forecast: {e}")
            return {
                "success": False,
                "error": str(e),
            }
```

## Publishing

1. Create a Python package
2. Include `cray.plugins` entry point:

```toml
# pyproject.toml
[project.entry-points."cray.plugins"]
my_plugin = "my_plugin:MyPlugin"
```

3. Publish to PyPI

## Need Help?

- Check existing plugins in `cray/plugins/builtin/`
- Review example workflows in `examples/`
- Open an issue on GitHub
