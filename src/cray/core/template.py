"""
Template engine for Cray workflows.

Supports Jinja2-style templates with workflow context variables.
"""

import re
from typing import Any, Dict, Optional
from datetime import datetime
from loguru import logger


class TemplateEngine:
    """
    Template engine for resolving variables in workflow parameters.
    
    Supports:
    - {{ input.key }} - Access workflow input
    - {{ steps.step_name.field }} - Access previous step outputs
    - {{ env.VAR_NAME }} - Access environment variables
    - {{ now }} - Current timestamp
    - {{ today }} - Today's date
    - Filters: | default('value'), | upper, | lower, | trim
    """
    
    # Pattern to match {{ expression }}
    TEMPLATE_PATTERN = re.compile(r'\{\{\s*(.+?)\s*\}\}')
    
    def __init__(self):
        """Initialize the template engine."""
        self._filters = {
            'default': lambda val, default='': val if val is not None else default,
            'upper': lambda val: str(val).upper(),
            'lower': lambda val: str(val).lower(),
            'trim': lambda val: str(val).strip(),
            'capitalize': lambda val: str(val).capitalize(),
            'length': lambda val: len(val) if hasattr(val, '__len__') else 0,
            'first': lambda val: val[0] if val and hasattr(val, '__getitem__') else None,
            'last': lambda val: val[-1] if val and hasattr(val, '__getitem__') else None,
            'join': lambda val, sep=',': sep.join(str(v) for v in val) if isinstance(val, list) else str(val),
            'json': lambda val: __import__('json').dumps(val),
            'date': lambda val, fmt='%Y-%m-%d': datetime.fromisoformat(str(val)).strftime(fmt) if val else '',
            'int': lambda val: int(val) if val else 0,
            'float': lambda val: float(val) if val else 0.0,
            'bool': lambda val: bool(val),
            'string': lambda val: str(val) if val is not None else '',
        }
    
    def render(
        self,
        template: Any,
        context: Dict[str, Any],
        env: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        Render a template with the given context.
        
        Args:
            template: The template value (string, dict, list, etc.)
            context: Workflow context with 'input' and 'steps'
            env: Optional environment variables dict
            
        Returns:
            Rendered value with templates resolved
        """
        if isinstance(template, str):
            return self._render_string(template, context, env)
        elif isinstance(template, dict):
            return {k: self.render(v, context, env) for k, v in template.items()}
        elif isinstance(template, list):
            return [self.render(item, context, env) for item in template]
        else:
            return template
    
    def _render_string(
        self,
        template: str,
        context: Dict[str, Any],
        env: Optional[Dict[str, str]] = None
    ) -> Any:
        """Render a string template."""
        # Check if the entire string is a single template
        match = self.TEMPLATE_PATTERN.fullmatch(template)
        if match:
            # Single expression - return the actual value (not string)
            return self._evaluate_expression(match.group(1), context, env)
        
        # Multiple or partial templates - string substitution
        def replace(match):
            result = self._evaluate_expression(match.group(1), context, env)
            return str(result) if result is not None else ''
        
        return self.TEMPLATE_PATTERN.sub(replace, template)
    
    def _evaluate_expression(
        self,
        expr: str,
        context: Dict[str, Any],
        env: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        Evaluate a template expression.
        
        Supports:
        - input.key
        - steps.step_name.field
        - steps.step_name.output.field
        - env.VAR_NAME
        - now, today
        - Filters: expr | filter | filter(arg)
        """
        try:
            # Handle filters
            parts = [p.strip() for p in expr.split('|')]
            base_expr = parts[0]
            filters = parts[1:] if len(parts) > 1 else []
            
            # Evaluate base expression
            value = self._resolve_value(base_expr, context, env)
            
            # Apply filters
            for filter_expr in filters:
                value = self._apply_filter(value, filter_expr)
            
            return value
            
        except Exception as e:
            logger.warning(f"Template evaluation failed for '{expr}': {e}")
            return None
    
    def _resolve_value(
        self,
        expr: str,
        context: Dict[str, Any],
        env: Optional[Dict[str, str]] = None
    ) -> Any:
        """Resolve a value expression."""
        expr = expr.strip()
        
        # Built-in variables
        if expr == 'now':
            return datetime.now().isoformat()
        if expr == 'today':
            return datetime.now().strftime('%Y-%m-%d')
        if expr == 'timestamp':
            return int(datetime.now().timestamp())
        if expr == 'uuid':
            import uuid
            return str(uuid.uuid4())
        
        # Input variables
        if expr.startswith('input.'):
            key = expr[6:]  # Remove 'input.'
            return self._get_nested(context.get('input', {}), key)
        
        if expr == 'input':
            return context.get('input', {})
        
        # Step outputs - context stores {success, output, error} per step
        if expr.startswith('steps.'):
            parts = expr[6:].split('.', 1)  # Remove 'steps.'
            step_name = parts[0]
            field = parts[1] if len(parts) > 1 else None
            
            step_data = context.get('steps', {}).get(step_name, {})
            
            if field:
                # Check special fields first
                if field in ("success", "output", "error"):
                    return step_data.get(field)
                # Otherwise look in step's output
                output = step_data.get("output", {})
                if isinstance(output, dict):
                    return output.get(field)
                return self._get_nested(output, field)
            return step_data
        
        # Environment variables
        if expr.startswith('env.'):
            key = expr[4:]  # Remove 'env.'
            if env:
                return env.get(key, '')
            # Fallback to os.environ
            import os
            return os.environ.get(key, '')

        # Secrets (secure credential access)
        if expr.startswith('secrets.'):
            key = expr[8:]  # Remove 'secrets.'
            from cray.core.secrets import get_secret
            return get_secret(key)

        # Literal values
        if expr == 'true':
            return True
        if expr == 'false':
            return False
        if expr == 'null' or expr == 'none':
            return None
        
        # Quoted strings
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]
        
        # Numbers
        try:
            if '.' in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass
        
        # Unknown expression
        logger.debug(f"Unknown expression: {expr}")
        return None
    
    def _get_nested(self, obj: Any, path: str) -> Any:
        """Get a nested value using dot notation."""
        if not path:
            return obj
        
        parts = path.split('.')
        current = obj
        
        for part in parts:
            if current is None:
                return None
            
            # Handle array index: items[0]
            if '[' in part and part.endswith(']'):
                name = part[:part.index('[')]
                index = int(part[part.index('[') + 1:part.index(']')])
                current = current.get(name, []) if isinstance(current, dict) else current
                current = current[index] if index < len(current) else None
            elif isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        
        return current
    
    def _apply_filter(self, value: Any, filter_expr: str) -> Any:
        """Apply a filter to a value."""
        # Parse filter name and arguments
        match = re.match(r'(\w+)(?:\((.+)\))?', filter_expr.strip())
        if not match:
            return value
        
        filter_name = match.group(1)
        filter_arg = match.group(2)
        
        if filter_name not in self._filters:
            logger.warning(f"Unknown filter: {filter_name}")
            return value
        
        filter_func = self._filters[filter_name]
        
        try:
            if filter_arg:
                # Parse argument (handle quoted strings)
                if (filter_arg.startswith('"') and filter_arg.endswith('"')) or \
                   (filter_arg.startswith("'") and filter_arg.endswith("'")):
                    filter_arg = filter_arg[1:-1]
                return filter_func(value, filter_arg)
            return filter_func(value)
        except Exception as e:
            logger.warning(f"Filter '{filter_name}' failed: {e}")
            return value
    
    def add_filter(self, name: str, func: callable) -> None:
        """Add a custom filter."""
        self._filters[name] = func


# Global template engine instance
_engine: Optional[TemplateEngine] = None


def get_engine() -> TemplateEngine:
    """Get the global template engine instance."""
    global _engine
    if _engine is None:
        _engine = TemplateEngine()
    return _engine


def render(
    template: Any,
    context: Dict[str, Any],
    env: Optional[Dict[str, str]] = None
) -> Any:
    """
    Render a template with the given context.
    
    Convenience function using the global engine.
    """
    return get_engine().render(template, context, env)
