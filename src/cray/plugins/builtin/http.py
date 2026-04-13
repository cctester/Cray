"""
HTTP plugin - make HTTP requests.
"""

import asyncio
import json
from typing import Dict, Any, Optional
from loguru import logger

from cray.plugins import Plugin


class HttpPlugin(Plugin):
    """Plugin for making HTTP requests."""
    
    name = "http"
    description = "Make HTTP requests"
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an HTTP action."""
        
        if action == "get":
            return await self._request("GET", params)
        elif action == "post":
            return await self._request("POST", params)
        elif action == "put":
            return await self._request("PUT", params)
        elif action == "delete":
            return await self._request("DELETE", params)
        elif action == "request":
            method = params.get("method", "GET")
            return await self._request(method, params)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _request(
        self, 
        method: str, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make an HTTP request."""
        
        url = params.get("url")
        if not url:
            raise ValueError("Missing required parameter: url")
        
        headers = params.get("headers", {})
        timeout = params.get("timeout", 30)
        
        # Prepare body
        body = None
        if "json" in params:
            body = json.dumps(params["json"]).encode()
            headers["Content-Type"] = "application/json"
        elif "body" in params:
            body = params["body"].encode() if isinstance(params["body"], str) else params["body"]
        
        logger.debug(f"HTTP {method} {url}")
        
        try:
            # Use aiohttp if available, otherwise fall back to urllib
            try:
                import aiohttp
                
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method=method,
                        url=url,
                        headers=headers,
                        data=body,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as response:
                        response_text = await response.text()
                        
                        # Try to parse JSON
                        try:
                            response_data = await response.json()
                        except:
                            response_data = response_text
                        
                        return {
                            "url": url,
                            "method": method,
                            "status_code": response.status,
                            "headers": dict(response.headers),
                            "body": response_data,
                            "success": 200 <= response.status < 300
                        }
                        
            except ImportError:
                # Fallback to urllib (sync, run in executor)
                import urllib.request
                import urllib.error
                
                def sync_request():
                    req = urllib.request.Request(url, method=method)
                    for key, value in headers.items():
                        req.add_header(key, value)
                    
                    try:
                        with urllib.request.urlopen(req, body, timeout=timeout) as response:
                            return {
                                "url": url,
                                "method": method,
                                "status_code": response.status,
                                "headers": dict(response.headers),
                                "body": response.read().decode(),
                                "success": True
                            }
                    except urllib.error.HTTPError as e:
                        return {
                            "url": url,
                            "method": method,
                            "status_code": e.code,
                            "headers": dict(e.headers) if e.headers else {},
                            "body": e.read().decode(),
                            "success": False
                        }
                
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, sync_request)
                
        except asyncio.TimeoutError:
            return {
                "url": url,
                "method": method,
                "success": False,
                "error": f"Request timed out after {timeout}s"
            }
        except Exception as e:
            return {
                "url": url,
                "method": method,
                "success": False,
                "error": str(e)
            }
