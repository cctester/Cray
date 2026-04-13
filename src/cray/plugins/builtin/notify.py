"""
Notify plugin - send notifications to various services.
"""

import asyncio
from typing import Dict, Any
from loguru import logger

from cray.plugins import Plugin


class NotifyPlugin(Plugin):
    """Plugin for sending notifications."""
    
    name = "notify"
    description = "Send notifications to Slack, Discord, Telegram, etc."
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a notification action."""
        
        actions = {
            "slack": self._send_slack,
            "discord": self._send_discord,
            "telegram": self._send_telegram,
            "webhook": self._send_webhook,
            "desktop": self._send_desktop,
        }
        
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        
        return await actions[action](params)
    
    async def _send_slack(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a Slack notification via webhook."""
        webhook_url = params.get("webhook_url")
        text = params.get("text", "")
        blocks = params.get("blocks")
        
        if not webhook_url:
            raise ValueError("Missing required parameter: webhook_url")
        
        payload = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        
        return await self._post_webhook(webhook_url, payload)
    
    async def _send_discord(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a Discord notification via webhook."""
        webhook_url = params.get("webhook_url")
        content = params.get("content", "")
        embeds = params.get("embeds")
        username = params.get("username", "Cray Bot")
        
        if not webhook_url:
            raise ValueError("Missing required parameter: webhook_url")
        
        payload = {
            "content": content,
            "username": username,
        }
        if embeds:
            payload["embeds"] = embeds
        
        return await self._post_webhook(webhook_url, payload)
    
    async def _send_telegram(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a Telegram message."""
        bot_token = params.get("bot_token")
        chat_id = params.get("chat_id")
        text = params.get("text", "")
        parse_mode = params.get("parse_mode", "HTML")
        
        if not bot_token or not chat_id:
            raise ValueError("Missing required parameters: bot_token, chat_id")
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        
        return await self._post_json(url, payload)
    
    async def _send_webhook(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a generic webhook notification."""
        url = params.get("url")
        payload = params.get("payload", {})
        headers = params.get("headers", {})
        
        if not url:
            raise ValueError("Missing required parameter: url")
        
        return await self._post_json(url, payload, headers)
    
    async def _send_desktop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a desktop notification."""
        title = params.get("title", "Cray")
        message = params.get("message", "")
        
        try:
            # Try using notify-send (Linux)
            proc = await asyncio.create_subprocess_exec(
                "notify-send", title, message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            
            return {
                "title": title,
                "message": message,
                "success": proc.returncode == 0,
            }
        except FileNotFoundError:
            # notify-send not available
            logger.warning("Desktop notifications not available (notify-send not found)")
            return {
                "title": title,
                "message": message,
                "success": False,
                "error": "notify-send not available",
            }
    
    async def _post_webhook(self, url: str, payload: Dict) -> Dict[str, Any]:
        """Post to a webhook URL."""
        return await self._post_json(url, payload)
    
    async def _post_json(
        self, 
        url: str, 
        payload: Dict,
        headers: Dict = None
    ) -> Dict[str, Any]:
        """Post JSON to a URL."""
        import json
        
        headers = headers or {}
        headers["Content-Type"] = "application/json"
        
        try:
            # Use urllib if aiohttp not available
            try:
                import aiohttp
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, 
                        json=payload, 
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        response_text = await response.text()
                        
                        return {
                            "status_code": response.status,
                            "response": response_text,
                            "success": 200 <= response.status < 300,
                        }
                        
            except ImportError:
                import urllib.request
                
                def sync_post():
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode(),
                        headers=headers,
                        method="POST",
                    )
                    
                    with urllib.request.urlopen(req, timeout=30) as response:
                        return {
                            "status_code": response.status,
                            "response": response.read().decode(),
                            "success": True,
                        }
                
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, sync_post)
                
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return {
                "success": False,
                "error": str(e),
            }
