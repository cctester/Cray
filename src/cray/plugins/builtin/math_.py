"""
Math plugin - mathematical operations.
"""

import math
import random
from typing import Dict, Any, List, Union
from loguru import logger

from cray.plugins import Plugin


class MathPlugin(Plugin):
    """Plugin for mathematical operations."""
    
    name = "math"
    description = "Perform mathematical calculations"
    
    @property
    def actions(self):
        return {
            "calculate": {"description": "Calculate expression", "params": [{"name": "expr", "type": "string", "required": True, "description": "Math expression"}]},
            "sum": {"description": "Sum values", "params": [{"name": "values", "type": "array", "required": True, "description": "Array of numbers"}]},
            "average": {"description": "Calculate average", "params": [{"name": "values", "type": "array", "required": True, "description": "Array of numbers"}]},
            "min": {"description": "Get minimum", "params": [{"name": "values", "type": "array", "required": True, "description": "Array of numbers"}]},
            "max": {"description": "Get maximum", "params": [{"name": "values", "type": "array", "required": True, "description": "Array of numbers"}]},
            "round": {"description": "Round number", "params": [{"name": "value", "type": "number", "required": True, "description": "Number to round"}, {"name": "decimals", "type": "number", "required": False, "description": "Number of decimals"}]},
        }
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a math action."""
        
        actions = {
            "calculate": self._calculate,
            "sum": self._sum,
            "average": self._average,
            "min": self._min,
            "max": self._max,
            "round": self._round,
            "random": self._random,
            "format": self._format,
        }
        
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        
        return await actions[action](params)
    
    async def _calculate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a mathematical expression."""
        expression = params.get("expression", "")
        variables = params.get("variables", {})
        
        try:
            # Safe evaluation with limited builtins
            allowed_names = {
                "abs": abs, "round": round, "min": min, "max": max,
                "sum": sum, "len": len,
                "pi": math.pi, "e": math.e,
                "sqrt": math.sqrt, "pow": math.pow,
                "sin": math.sin, "cos": math.cos, "tan": math.tan,
                "log": math.log, "log10": math.log10,
                "floor": math.floor, "ceil": math.ceil,
                **variables,
            }
            
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            
            return {
                "expression": expression,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "expression": expression,
                "success": False,
                "error": str(e),
            }
    
    async def _sum(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sum a list of numbers."""
        numbers = params.get("numbers", [])
        
        try:
            result = sum(numbers)
            return {
                "numbers": numbers,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _average(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate average of numbers."""
        numbers = params.get("numbers", [])
        
        try:
            if not numbers:
                return {
                    "numbers": numbers,
                    "result": 0,
                    "success": True,
                }
            
            result = sum(numbers) / len(numbers)
            return {
                "numbers": numbers,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _min(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find minimum value."""
        numbers = params.get("numbers", [])
        
        try:
            result = min(numbers) if numbers else None
            return {
                "numbers": numbers,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _max(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find maximum value."""
        numbers = params.get("numbers", [])
        
        try:
            result = max(numbers) if numbers else None
            return {
                "numbers": numbers,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _round(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Round a number."""
        number = params.get("number", 0)
        decimals = params.get("decimals", 0)
        
        try:
            result = round(number, decimals)
            return {
                "number": number,
                "decimals": decimals,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _random(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate random number."""
        min_val = params.get("min", 0)
        max_val = params.get("max", 100)
        count = params.get("count", 1)
        
        try:
            if count == 1:
                result = random.uniform(min_val, max_val)
            else:
                result = [random.uniform(min_val, max_val) for _ in range(count)]
            
            return {
                "min": min_val,
                "max": max_val,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _format(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Format a number."""
        number = params.get("number", 0)
        format_type = params.get("format", "number")
        
        try:
            if format_type == "currency":
                locale = params.get("locale", "en_US")
                symbol = params.get("symbol", "$")
                decimals = params.get("decimals", 2)
                result = f"{symbol}{number:,.{decimals}f}"
            elif format_type == "percent":
                decimals = params.get("decimals", 1)
                result = f"{number * 100:.{decimals}f}%"
            elif format_type == "scientific":
                result = f"{number:e}"
            else:
                decimals = params.get("decimals", 2)
                result = f"{number:,.{decimals}f}"
            
            return {
                "number": number,
                "format": format_type,
                "result": result,
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
