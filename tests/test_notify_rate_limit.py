"""Tests for NotifyPlugin rate limiting."""

import time
import pytest
from unittest.mock import patch, AsyncMock

from cray.plugins.builtin.notify import NotifyPlugin, _RateLimiter


# ---------------------------------------------------------------------------
# _RateLimiter unit tests
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """Tests for the _RateLimiter token-bucket + cooldown logic."""

    def setup_method(self):
        self.limiter = _RateLimiter(max_calls=3, period=10.0, cooldown=0.0)

    def test_allows_within_limit(self):
        params = {"webhook_url": "https://hooks.slack.com/test"}
        for i in range(3):
            reason = self.limiter.check("slack", params)
            assert reason is None, f"Call {i+1} should be allowed"

    def test_blocks_over_limit(self):
        params = {"webhook_url": "https://hooks.slack.com/test"}
        for _ in range(3):
            self.limiter.check("slack", params)
        reason = self.limiter.check("slack", params)
        assert reason is not None
        assert "Rate-limited" in reason
        assert "max 3" in reason

    def test_different_destinations_independent(self):
        params_a = {"webhook_url": "https://hooks.slack.com/a"}
        params_b = {"webhook_url": "https://hooks.slack.com/b"}
        for _ in range(3):
            self.limiter.check("slack", params_a)
        # Destination B should still be allowed
        reason = self.limiter.check("slack", params_b)
        assert reason is None

    def test_cooldown_blocks_burst(self):
        limiter = _RateLimiter(max_calls=100, period=60.0, cooldown=2.0)
        params = {"webhook_url": "https://hooks.slack.com/test"}
        reason1 = limiter.check("slack", params)
        assert reason1 is None
        # Immediate second call should be blocked by cooldown
        reason2 = limiter.check("slack", params)
        assert reason2 is not None
        assert "cooldown" in reason2

    def test_cooldown_allows_after_wait(self):
        limiter = _RateLimiter(max_calls=100, period=60.0, cooldown=0.05)
        params = {"webhook_url": "https://hooks.slack.com/test"}
        limiter.check("slack", params)
        time.sleep(0.06)
        reason = limiter.check("slack", params)
        assert reason is None

    def test_telegram_key_includes_chat_id(self):
        params_a = {"bot_token": "tok", "chat_id": "111"}
        params_b = {"bot_token": "tok", "chat_id": "222"}
        # Use up quota for chat 111
        limiter = _RateLimiter(max_calls=1, period=60.0, cooldown=0.0)
        limiter.check("telegram", params_a)
        # chat 222 should still be allowed (different key)
        reason = limiter.check("telegram", params_b)
        assert reason is None

    def test_webhook_key_includes_url(self):
        params_a = {"url": "https://example.com/a"}
        params_b = {"url": "https://example.com/b"}
        limiter = _RateLimiter(max_calls=1, period=60.0, cooldown=0.0)
        limiter.check("webhook", params_a)
        reason = limiter.check("webhook", params_b)
        assert reason is None

    def test_reset_all(self):
        params = {"webhook_url": "https://hooks.slack.com/test"}
        for _ in range(3):
            self.limiter.check("slack", params)
        self.limiter.reset()
        reason = self.limiter.check("slack", params)
        assert reason is None

    def test_reset_specific_key(self):
        params_a = {"webhook_url": "https://hooks.slack.com/a"}
        params_b = {"webhook_url": "https://hooks.slack.com/b"}
        for _ in range(3):
            self.limiter.check("slack", params_a)
            self.limiter.check("slack", params_b)
        # Reset only A
        self.limiter.reset("slack:https://hooks.slack.com/a")
        reason_a = self.limiter.check("slack", params_a)
        reason_b = self.limiter.check("slack", params_b)
        assert reason_a is None
        assert reason_b is not None

    def test_window_expiry(self):
        limiter = _RateLimiter(max_calls=1, period=0.1, cooldown=0.0)
        params = {"webhook_url": "https://hooks.slack.com/test"}
        limiter.check("slack", params)
        reason = limiter.check("slack", params)
        assert reason is not None
        # After the window expires, should be allowed again
        time.sleep(0.15)
        reason = limiter.check("slack", params)
        assert reason is None


# ---------------------------------------------------------------------------
# NotifyPlugin integration tests (with HTTP mocked)
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_limiter():
    """Provide a fresh rate limiter and patch the module-level one."""
    limiter = _RateLimiter(max_calls=3, period=60.0, cooldown=0.0)
    with patch("cray.plugins.builtin.notify._rate_limiter", limiter):
        yield limiter


@pytest.fixture
def plugin(fresh_limiter):
    return NotifyPlugin()


@pytest.mark.asyncio
async def test_rate_limit_returns_error(plugin, fresh_limiter):
    """When rate-limited, execute returns success=False with rate_limited=True."""
    params = {"webhook_url": "https://hooks.slack.com/test", "text": "hi"}
    # Exhaust the bucket
    for _ in range(3):
        await plugin.execute("slack", params, {})
    # 4th call should be rate-limited
    result = await plugin.execute("slack", params, {})
    assert result["success"] is False
    assert result.get("rate_limited") is True
    assert "Rate-limited" in result["error"]


@pytest.mark.asyncio
async def test_rate_limit_does_not_affect_other_dest(plugin, fresh_limiter):
    """Rate-limiting one destination should not block another."""
    params_a = {"webhook_url": "https://hooks.slack.com/a", "text": "hi"}
    params_b = {"webhook_url": "https://hooks.slack.com/b", "text": "hi"}
    for _ in range(3):
        await plugin.execute("slack", params_a, {})
    # Destination B should still work
    with patch.object(plugin, "_post_webhook", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {"success": True, "status_code": 200}
        result = await plugin.execute("slack", params_b, {})
        assert result["success"] is True


@pytest.mark.asyncio
async def test_setup_reconfigures_limiter():
    """Plugin.setup() should replace the module-level rate limiter."""
    config = {
        "rate_limit_max_calls": 1,
        "rate_limit_period": 10.0,
        "rate_limit_cooldown": 0.0,
    }
    p = NotifyPlugin()
    p.setup(config)
    from cray.plugins.builtin.notify import _rate_limiter as lim
    assert lim.max_calls == 1
    assert lim.period == 10.0
    # Reset for other tests
    p.setup({"rate_limit_max_calls": 20, "rate_limit_period": 60.0, "rate_limit_cooldown": 1.0})


@pytest.mark.asyncio
async def test_unknown_action_raises(plugin, fresh_limiter):
    """Unknown action should raise ValueError (not rate-limited)."""
    with pytest.raises(ValueError, match="Unknown action"):
        await plugin.execute("carrier_pigeon", {}, {})
