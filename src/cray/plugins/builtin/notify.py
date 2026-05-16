"""
Notify plugin - send notifications to various services.
"""

import asyncio
import time
from typing import Dict, Any, Optional
from loguru import logger

from cray.plugins import Plugin


class _RateLimiter:
    """Token-bucket rate limiter keyed by destination.

    Prevents notification floods when a workflow sends many notify
    steps to the same webhook/chat in quick succession.
    """

    def __init__(
        self,
        max_calls: int = 20,
        period: float = 60.0,
        cooldown: float = 1.0,
    ):
        """
        Args:
            max_calls: Maximum notifications per *period* per destination.
            period: Time window in seconds for the bucket.
            cooldown: Minimum seconds between consecutive sends to the
                      same destination (anti-burst).
        """
        self.max_calls = max_calls
        self.period = period
        self.cooldown = cooldown
        self._buckets: Dict[str, list] = {}   # key -> [timestamps]
        self._last_sent: Dict[str, float] = {}  # key -> last send time

    def _key(self, action: str, params: Dict[str, Any]) -> str:
        """Build a dedup key from action + destination identifier."""
        if action == "slack":
            return f"slack:{params.get('webhook_url', '')}"
        if action == "discord":
            return f"discord:{params.get('webhook_url', '')}"
        if action == "telegram":
            return f"telegram:{params.get('bot_token', '')}:{params.get('chat_id', '')}"
        if action == "webhook":
            return f"webhook:{params.get('url', '')}"
        if action == "desktop":
            return "desktop:local"
        return f"{action}:unknown"

    def check(self, action: str, params: Dict[str, Any]) -> Optional[str]:
        """Check whether the notification is allowed.

        Returns ``None`` if allowed, or a reason string if rate-limited.
        """
        key = self._key(action, params)
        now = time.monotonic()

        # --- cooldown (anti-burst) ---
        last = self._last_sent.get(key, 0.0)
        if now - last < self.cooldown:
            remaining = self.cooldown - (now - last)
            return (
                f"Rate-limited: cooldown {self.cooldown}s between sends "
                f"to {key} ({remaining:.1f}s remaining)"
            )

        # --- token bucket (max_calls / period) ---
        timestamps = self._buckets.setdefault(key, [])
        # Prune timestamps outside the window
        cutoff = now - self.period
        self._buckets[key] = [t for t in timestamps if t > cutoff]
        timestamps = self._buckets[key]

        if len(timestamps) >= self.max_calls:
            oldest = timestamps[0]
            wait = self.period - (now - oldest)
            return (
                f"Rate-limited: max {self.max_calls} notifications per "
                f"{self.period}s to {key} (retry after {wait:.1f}s)"
            )

        # Record the send
        timestamps.append(now)
        self._last_sent[key] = now
        return None

    def reset(self, key: Optional[str] = None) -> None:
        """Reset rate-limit state. If *key* is None, reset all."""
        if key is None:
            self._buckets.clear()
            self._last_sent.clear()
        else:
            self._buckets.pop(key, None)
            self._last_sent.pop(key, None)


# Module-level rate limiter shared across all NotifyPlugin instances.
# Configurable via plugin setup().
_rate_limiter = _RateLimiter()


class NotifyPlugin(Plugin):
    """Plugin for sending notifications."""

    name = "notify"
    description = "Send notifications to Slack, Discord, Telegram, etc."

    def setup(self, config: Dict[str, Any]) -> None:
        """Configure rate limiting from plugin config.

        Expected config keys (all optional):
            rate_limit_max_calls  – int, default 20
            rate_limit_period     – float seconds, default 60
            rate_limit_cooldown   – float seconds, default 1
        """
        global _rate_limiter
        max_calls = config.get("rate_limit_max_calls", 20)
        period = config.get("rate_limit_period", 60.0)
        cooldown = config.get("rate_limit_cooldown", 1.0)
        _rate_limiter = _RateLimiter(
            max_calls=max_calls,
            period=period,
            cooldown=cooldown,
        )
        logger.info(
            f"Notify rate limiter configured: "
            f"{max_calls} calls/{period}s, cooldown {cooldown}s"
        )

    @property
    def actions(self):
        return {
            "slack": {"description": "Send Slack notification", "params": [{"name": "webhook", "type": "string", "required": True, "description": "Webhook URL"}, {"name": "message", "type": "string", "required": True, "description": "Message"}]},
            "discord": {"description": "Send Discord notification", "params": [{"name": "webhook", "type": "string", "required": True, "description": "Webhook URL"}, {"name": "message", "type": "string", "required": True, "description": "Message"}]},
            "telegram": {"description": "Send Telegram notification", "params": [{"name": "bot_token", "type": "string", "required": True, "description": "Bot token"}, {"name": "chat_id", "type": "string", "required": True, "description": "Chat ID"}, {"name": "message", "type": "string", "required": True, "description": "Message"}]},
            "webhook": {"description": "Send generic webhook", "params": [{"name": "url", "type": "string", "required": True, "description": "URL"}, {"name": "method", "type": "string", "required": False, "description": "HTTP method"}]},
        }

    async def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a notification action."""

        # --- Rate limit check ---
        reason = _rate_limiter.check(action, params)
        if reason is not None:
            logger.warning(f"Notification rate-limited: {reason}")
            return {
                "success": False,
                "error": reason,
                "rate_limited": True,
            }

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

                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, sync_post)

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return {
                "success": False,
                "error": str(e),
            }
