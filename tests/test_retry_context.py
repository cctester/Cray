"""Tests for #10 — retry with fresh context per attempt."""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cray.core.runner import Runner
from cray.core.workflow import Workflow, Step
from cray.core.task import TaskStatus
from cray.plugins import PluginManager


# ── Helper: a plugin that records what context it sees each call ──────

class _RecordingPlugin:
    """A fake plugin that records the context it receives and can
    fail a configurable number of times before succeeding."""

    name = "recorder"

    def __init__(self, fail_count: int = 0):
        self.fail_count = fail_count
        self.call_count = 0
        self.seen_contexts: list = []

    async def execute(self, action: str, params: Dict[str, Any],
                       context: Dict[str, Any]) -> Dict[str, Any]:
        self.call_count += 1
        # Snapshot the parts we care about
        snapshot = {
            "call": self.call_count,
            "retry": context.get("retry"),
            "step_output": context.get("steps", {}).get("test-step"),
        }
        self.seen_contexts.append(snapshot)

        if self.call_count <= self.fail_count:
            raise RuntimeError(f"intentional failure #{self.call_count}")

        return {"ok": True, "attempt": self.call_count}


class _RecordingPluginManager(PluginManager):
    """PluginManager that returns our recording plugin."""

    def __init__(self, plugin):
        self._plugin = plugin

    def get_plugin(self, name: str):
        if name == "recorder":
            return self._plugin
        return None


# ── Tests ─────────────────────────────────────────────────────────────

def test_retry_injects_attempt_number():
    """Each retry attempt should see retry.attempt incrementing."""
    async def _test():
        plugin = _RecordingPlugin(fail_count=2)
        runner = Runner(plugin_manager=_RecordingPluginManager(plugin))

        step = Step(
            name="test-step",
            plugin="recorder",
            action="run",
            retry=3,
            retry_delay=0,
        )
        workflow = Workflow(name="retry-test", steps=[step])

        task = await runner.run(workflow)

        assert task.status == TaskStatus.SUCCESS, f"Expected success, got {task.status}"
        assert plugin.call_count == 3  # 1 initial + 2 retries

        # First call (initial) — no retry context
        assert plugin.seen_contexts[0]["retry"] is None, \
            f"Initial call should have no retry context, got {plugin.seen_contexts[0]['retry']}"

        # Second call (retry 1)
        r1 = plugin.seen_contexts[1]["retry"]
        assert r1 is not None, "Retry 1 should have retry context"
        assert r1["attempt"] == 1, f"Retry 1 attempt should be 1, got {r1['attempt']}"
        assert r1["max_retries"] == 3

        # Third call (retry 2)
        r2 = plugin.seen_contexts[2]["retry"]
        assert r2 is not None, "Retry 2 should have retry context"
        assert r2["attempt"] == 2, f"Retry 2 attempt should be 2, got {r2['attempt']}"

        print("  ✅ retry_injects_attempt_number")

    asyncio.run(_test())


def test_retry_injects_last_error():
    """Each retry should see the error from the previous attempt."""
    async def _test():
        plugin = _RecordingPlugin(fail_count=1)
        runner = Runner(plugin_manager=_RecordingPluginManager(plugin))

        step = Step(
            name="test-step",
            plugin="recorder",
            action="run",
            retry=2,
            retry_delay=0,
        )
        workflow = Workflow(name="retry-error-test", steps=[step])

        task = await runner.run(workflow)

        assert task.status == TaskStatus.SUCCESS

        # Retry 1 should carry the error from the initial (failed) call
        r1 = plugin.seen_contexts[1]["retry"]
        assert r1 is not None
        assert "intentional failure" in r1["last_error"], \
            f"Expected last_error to mention failure, got: {r1['last_error']}"

        print("  ✅ retry_injects_last_error")

    asyncio.run(_test())


def test_retry_updates_step_context():
    """The steps.<name> entry should reflect the latest failure before retry."""
    async def _test():
        plugin = _RecordingPlugin(fail_count=1)
        runner = Runner(plugin_manager=_RecordingPluginManager(plugin))

        step = Step(
            name="test-step",
            plugin="recorder",
            action="run",
            retry=2,
            retry_delay=0,
        )
        workflow = Workflow(name="retry-step-ctx-test", steps=[step])

        task = await runner.run(workflow)

        assert task.status == TaskStatus.SUCCESS

        # On the retry call, steps.test-step should show the failure
        step_ctx = plugin.seen_contexts[1]["step_output"]
        assert step_ctx is not None, "Retry should see step context"
        assert step_ctx["success"] is False
        assert "intentional failure" in (step_ctx.get("error") or "")

        print("  ✅ retry_updates_step_context")

    asyncio.run(_test())


def test_retry_context_does_not_leak_to_next_step():
    """After a step succeeds on retry, the 'retry' key should not be
    visible in the context of subsequent steps."""
    async def _test():
        contexts_seen = []

        class TwoStepPlugin:
            name = "twostep"

            def __init__(self):
                self.call_count = 0

            async def execute(self, action, params, context):
                self.call_count += 1
                contexts_seen.append({k: context.get(k) for k in ("retry",)})
                if self.call_count == 1:
                    raise RuntimeError("fail first step on first try")
                return {"step": self.call_count}

        plugin = TwoStepPlugin()
        runner = Runner(plugin_manager=_RecordingPluginManager(plugin))

        steps = [
            Step(name="s1", plugin="twostep", action="run", retry=1, retry_delay=0,
                 continue_on_error=True),
            Step(name="s2", plugin="twostep", action="run", retry=0),
        ]
        workflow = Workflow(name="leak-test", steps=steps)

        task = await runner.run(workflow)
        assert task.status == TaskStatus.SUCCESS

        # s1 initial call — no retry
        assert contexts_seen[0]["retry"] is None

        # s1 retry call — has retry context
        assert contexts_seen[1]["retry"] is not None

        # s2 (next step) — retry context should NOT leak
        assert contexts_seen[2]["retry"] is None, \
            f"'retry' leaked into next step: {contexts_seen[2]['retry']}"

        print("  ✅ retry_context_does_not_leak_to_next_step")

    asyncio.run(_test())


def test_no_retry_on_success():
    """If the step succeeds on the first try, no retry context is added."""
    async def _test():
        plugin = _RecordingPlugin(fail_count=0)
        runner = Runner(plugin_manager=_RecordingPluginManager(plugin))

        step = Step(
            name="test-step",
            plugin="recorder",
            action="run",
            retry=3,
            retry_delay=0,
        )
        workflow = Workflow(name="no-retry-test", steps=[step])

        task = await runner.run(workflow)

        assert task.status == TaskStatus.SUCCESS
        assert plugin.call_count == 1
        assert plugin.seen_contexts[0]["retry"] is None

        print("  ✅ no_retry_on_success")

    asyncio.run(_test())


def test_all_retries_exhausted():
    """When all retries are exhausted, the step should fail."""
    async def _test():
        plugin = _RecordingPlugin(fail_count=999)  # always fails
        runner = Runner(plugin_manager=_RecordingPluginManager(plugin))

        step = Step(
            name="test-step",
            plugin="recorder",
            action="run",
            retry=2,
            retry_delay=0,
            continue_on_error=True,
        )
        workflow = Workflow(name="exhaust-test", steps=[step])

        task = await runner.run(workflow)

        # 1 initial + 2 retries = 3 calls
        assert plugin.call_count == 3
        # Last retry attempt number should be 2
        last_retry = plugin.seen_contexts[-1]["retry"]
        assert last_retry["attempt"] == 2

        print("  ✅ all_retries_exhausted")

    asyncio.run(_test())


if __name__ == "__main__":
    print("Running #10 retry-with-context tests...")
    test_retry_injects_attempt_number()
    test_retry_injects_last_error()
    test_retry_updates_step_context()
    test_retry_context_does_not_leak_to_next_step()
    test_no_retry_on_success()
    test_all_retries_exhausted()
    print("\n✅ All retry-context tests passed!")
