"""
Redis plugin for Cray - provides basic Redis operations.
"""

from typing import Dict, Any
from loguru import logger

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None

from cray.plugins import Plugin


class RedisPlugin(Plugin):
    """Plugin for Redis operations."""

    name = "redis"
    description = "Redis cache and queue operations"
    
    @property
    def actions(self):
        return {
            "connect": {"description": "Connect to Redis", "params": [{"name": "host", "type": "string", "required": True, "description": "Redis host"}, {"name": "port", "type": "number", "required": False, "description": "Redis port"}]},
            "get": {"description": "Get value", "params": [{"name": "key", "type": "string", "required": True, "description": "Key"}]},
            "set": {"description": "Set value", "params": [{"name": "key", "type": "string", "required": True, "description": "Key"}, {"name": "value", "type": "string", "required": True, "description": "Value"}]},
            "delete": {"description": "Delete key", "params": [{"name": "key", "type": "string", "required": True, "description": "Key"}]},
            "queue": {"description": "Push to queue", "params": [{"name": "queue", "type": "string", "required": True, "description": "Queue name"}, {"name": "value", "type": "string", "required": True, "description": "Value"}]},
        }
    
    async def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a Redis action."""

        if not REDIS_AVAILABLE:
            return {
                "success": False,
                "error": "Redis plugin requires 'redis' package. Install with: pip install redis"
            }

        actions = {
            "connect": self._connect,
            "get": self._get,
            "set": self._set,
            "delete": self._delete,
            "disconnect": self._disconnect,
            "exists": self._exists,
            "keys": self._keys,
            "flushdb": self._flushdb,
        }

        if action not in actions:
            raise ValueError(f"Unknown action: {action}")

        return await actions[action](params)

    async def _connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Connect to Redis server."""
        host = params.get("host", "localhost")
        port = params.get("port", 6379)
        db = params.get("db", 0)
        password = params.get("password", None)
        connection_name = params.get("connection_name", "default")

        try:
            self.connections[connection_name] = aioredis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True
            )

            await self.connections[connection_name].ping()

            return {
                "success": True,
                "connection": connection_name
            }
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get a key from Redis."""
        connection_name = params.get("connection_name", "default")
        key = params.get("key")

        if not key:
            raise ValueError("Missing required parameter: key")

        try:
            redis = self.connections.get(connection_name)
            if not redis:
                raise ValueError(f"No connection found: {connection_name}")

            value = await redis.get(key)
            return {
                "success": True,
                "key": key,
                "value": value
            }
        except Exception as e:
            logger.error(f"Failed to get key: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _set(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set a key in Redis."""
        connection_name = params.get("connection_name", "default")
        key = params.get("key")
        value = params.get("value")
        expire = params.get("expire", None)

        if not key or value is None:
            raise ValueError("Missing required parameters: key, value")

        try:
            redis = self.connections.get(connection_name)
            if not redis:
                raise ValueError(f"No connection found: {connection_name}")

            await redis.set(key, value, ex=expire)
            return {
                "success": True,
                "key": key,
                "value": value
            }
        except Exception as e:
            logger.error(f"Failed to set key: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a key from Redis."""
        connection_name = params.get("connection_name", "default")
        key = params.get("key")

        if not key:
            raise ValueError("Missing required parameter: key")

        try:
            redis = self.connections.get(connection_name)
            if not redis:
                raise ValueError(f"No connection found: {connection_name}")

            await redis.delete(key)
            return {
                "success": True,
                "key": key
            }
        except Exception as e:
            logger.error(f"Failed to delete key: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _exists(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a key exists in Redis."""
        connection_name = params.get("connection_name", "default")
        key = params.get("key")

        if not key:
            raise ValueError("Missing required parameter: key")

        try:
            redis = self.connections.get(connection_name)
            if not redis:
                raise ValueError(f"No connection found: {connection_name}")

            exists = await redis.exists(key)
            return {
                "success": True,
                "key": key,
                "exists": bool(exists)
            }
        except Exception as e:
            logger.error(f"Failed to check key existence: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _keys(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List keys matching a pattern."""
        connection_name = params.get("connection_name", "default")
        pattern = params.get("pattern", "*")

        try:
            redis = self.connections.get(connection_name)
            if not redis:
                raise ValueError(f"No connection found: {connection_name}")

            keys = await redis.keys(pattern)
            return {
                "success": True,
                "keys": keys
            }
        except Exception as e:
            logger.error(f"Failed to list keys: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _flushdb(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Flush the database."""
        connection_name = params.get("connection_name", "default")

        try:
            redis = self.connections.get(connection_name)
            if not redis:
                raise ValueError(f"No connection found: {connection_name}")

            await redis.flushdb()
            return {
                "success": True
            }
        except Exception as e:
            logger.error(f"Failed to flush database: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _disconnect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Disconnect from Redis server."""
        connection_name = params.get("connection_name", "default")

        try:
            redis = self.connections.get(connection_name)
            if not redis:
                raise ValueError(f"No connection found: {connection_name}")

            await redis.aclose()
            del self.connections[connection_name]
            return {
                "success": True
            }
        except Exception as e:
            logger.error(f"Failed to disconnect: {e}")
            return {
                "success": False,
                "error": str(e)
            }