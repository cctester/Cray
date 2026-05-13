""" HTTP plugin - make HTTP requests.

Security notes:
- SSRF protection: blocks requests to private/internal IP ranges by default.
- Set `ssrf_protection=False` in config to disable (not recommended).
- Set `allowed_hosts` in config to restrict to specific hostnames.
"""

import asyncio
import ipaddress
import json
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse

from loguru import logger

from cray.plugins import Plugin

# Private/internal IP ranges to block by default
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local (AWS metadata)
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("0.0.0.0/8"),         # Current network
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
    ipaddress.ip_network("198.18.0.0/15"),     # Benchmark testing
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved
]

_PRIVATE_NETWORKS_V6 = [
    ipaddress.ip_network("::1/128"),           # Loopback
    ipaddress.ip_network("fc00::/7"),          # Unique local
    ipaddress.ip_network("fe80::/10"),         # Link-local
    ipaddress.ip_network("ff00::/8"),          # Multicast
]


class HttpPlugin(Plugin):
    """Plugin for making HTTP requests.

    Config options:
        ssrf_protection: Block requests to private/internal IPs (default: True)
        allowed_hosts: Set of allowed hostnames (if set, only these are allowed)
        timeout: Default request timeout in seconds (default: 30)
    """

    name = "http"
    description = "Make HTTP requests"

    def __init__(self):
        super().__init__()
        self._ssrf_protection: bool = True
        self._allowed_hosts: Optional[Set[str]] = None
        self._timeout: int = 30

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the HTTP plugin."""
        self._ssrf_protection = config.get("ssrf_protection", True)
        allowed = config.get("allowed_hosts")
        if allowed:
            self._allowed_hosts = set(allowed)
        self._timeout = config.get("timeout", 30)

    def _validate_url(self, url: str) -> None:
        """Validate URL against SSRF protection rules.

        Raises ValueError if the URL targets a blocked host/IP.
        """
        parsed = urlparse(url)

        if not parsed.scheme or not parsed.hostname:
            raise ValueError(f"Invalid URL: {url}")

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported scheme: {parsed.scheme}. Only http/https allowed.")

        # Check allowed hosts
        if self._allowed_hosts is not None:
            if parsed.hostname not in self._allowed_hosts:
                raise ValueError(
                    f"Host not in allowed list: {parsed.hostname}. "
                    f"Allowed: {self._allowed_hosts}"
                )

        # SSRF protection: resolve hostname and check against private ranges
        if self._ssrf_protection:
            import socket
            try:
                # Resolve hostname to check IP
                addr_info = socket.getaddrinfo(parsed.hostname, None)
                for family, _, _, _, sockaddr in addr_info:
                    ip_str = sockaddr[0]
                    try:
                        ip = ipaddress.ip_address(ip_str)
                        networks = _PRIVATE_NETWORKS_V6 if ip.version == 6 else _PRIVATE_NETWORKS
                        for network in networks:
                            if ip in network:
                                raise ValueError(
                                    f"SSRF protection: {parsed.hostname} resolves to "
                                    f"private/internal IP {ip}. "
                                    f"Set ssrf_protection=False to disable."
                                )
                    except ValueError as e:
                        if "SSRF protection" in str(e):
                            raise
                        # Not an IP address, skip
                        continue
            except socket.gaierror:
                # DNS resolution failed — let the request proceed and fail naturally
                pass

    @property
    def actions(self):
        return {
            "get": {"description": "Make GET request", "params": [
                {"name": "url", "type": "string", "required": True, "description": "URL to request"}
            ]},
            "post": {"description": "Make POST request", "params": [
                {"name": "url", "type": "string", "required": True, "description": "URL to request"},
                {"name": "body", "type": "string", "required": False, "description": "Request body"}
            ]},
            "put": {"description": "Make PUT request", "params": [
                {"name": "url", "type": "string", "required": True, "description": "URL to request"},
                {"name": "body", "type": "string", "required": False, "description": "Request body"}
            ]},
            "delete": {"description": "Make DELETE request", "params": [
                {"name": "url", "type": "string", "required": True, "description": "URL to request"}
            ]},
        }

    async def execute(
        self, action: str, params: Dict[str, Any], context: Dict[str, Any]
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
        self, method: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make an HTTP request."""
        url = params.get("url")
        if not url:
            raise ValueError("Missing required parameter: url")

        # Validate URL against SSRF rules
        self._validate_url(url)

        headers = params.get("headers", {})
        timeout = params.get("timeout", self._timeout)

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
                        # Read text once, then try JSON parse from text
                        response_text = await response.text()
                        try:
                            response_data = json.loads(response_text)
                        except (json.JSONDecodeError, ValueError):
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
                            resp_text = response.read().decode()
                            try:
                                resp_data = json.loads(resp_text)
                            except (json.JSONDecodeError, ValueError):
                                resp_data = resp_text
                            return {
                                "url": url,
                                "method": method,
                                "status_code": response.status,
                                "headers": dict(response.headers),
                                "body": resp_data,
                                "success": True
                            }
                    except urllib.error.HTTPError as e:
                        resp_text = e.read().decode()
                        try:
                            resp_data = json.loads(resp_text)
                        except (json.JSONDecodeError, ValueError):
                            resp_data = resp_text
                        return {
                            "url": url,
                            "method": method,
                            "status_code": e.code,
                            "headers": dict(e.headers) if e.headers else {},
                            "body": resp_data,
                            "success": False
                        }

                loop = asyncio.get_running_loop()
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
