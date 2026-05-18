import pytest
from cray.core.workflow import Step


class TestParallelExecution:
    def test_step_on_error_handler(self):
        """Test that on_error accepts a list of handler dicts."""
        step = Step(
            name='test_step',
            plugin='shell',
            action='run',
            on_error=[{'action': 'log', 'params': {'message': 'Custom error message'}}]
        )
        assert step.on_error == [{'action': 'log', 'params': {'message': 'Custom error message'}}]

    def test_step_on_error_default_none(self):
        """Test that on_error defaults to None."""
        step = Step(name='test_step', plugin='shell', action='run')
        assert step.on_error is None

    def test_step_continue_on_error_default(self):
        """Test that continue_on_error defaults to False."""
        step = Step(name='test_step', plugin='shell', action='run')
        assert step.continue_on_error is False
