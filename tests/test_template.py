"""
Tests for the template engine.
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from cray.core.template import TemplateEngine, render


class TestTemplateEngine:
    """Tests for TemplateEngine class."""

    @pytest.fixture
    def engine(self):
        return TemplateEngine()

    @pytest.fixture
    def context(self):
        return {
            "input": {
                "name": "test",
                "count": 5,
                "items": ["a", "b", "c"],
                "nested": {"key": "value"}
            },
            "steps": {
                "fetch": {
                    "success": True,
                    "data": {"id": 123, "name": "fetched"},
                    "count": 10
                },
                "process": {
                    "success": False,
                    "error": "Something went wrong"
                }
            }
        }

    # Basic rendering tests
    def test_render_string_literal(self, engine, context):
        """Test that plain strings pass through unchanged."""
        result = engine.render("Hello World", context)
        assert result == "Hello World"

    def test_render_number(self, engine, context):
        """Test that numbers pass through unchanged."""
        result = engine.render(42, context)
        assert result == 42

    def test_render_dict(self, engine, context):
        """Test rendering templates in dict values."""
        template = {"name": "{{ input.name }}", "count": "{{ input.count }}"}
        result = engine.render(template, context)
        assert result == {"name": "test", "count": 5}

    def test_render_list(self, engine, context):
        """Test rendering templates in list items."""
        template = ["{{ input.name }}", "{{ steps.fetch.count }}"]
        result = engine.render(template, context)
        assert result == ["test", 10]

    # Input variable tests
    def test_input_variable(self, engine, context):
        """Test accessing input variables."""
        result = engine.render("{{ input.name }}", context)
        assert result == "test"

    def test_input_nested(self, engine, context):
        """Test accessing nested input values."""
        result = engine.render("{{ input.nested.key }}", context)
        assert result == "value"

    def test_input_missing(self, engine, context):
        """Test accessing missing input returns None."""
        result = engine.render("{{ input.missing }}", context)
        assert result is None

    # Step output tests
    def test_step_output(self, engine, context):
        """Test accessing step outputs."""
        result = engine.render("{{ steps.fetch.count }}", context)
        assert result == 10

    def test_step_nested_output(self, engine, context):
        """Test accessing nested step outputs."""
        result = engine.render("{{ steps.fetch.data.name }}", context)
        assert result == "fetched"

    def test_step_success(self, engine, context):
        """Test accessing step success status."""
        result = engine.render("{{ steps.fetch.success }}", context)
        assert result is True

    # Built-in variables
    def test_now_variable(self, engine, context):
        """Test the 'now' built-in variable."""
        with patch('cray.core.template.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 13, 12, 0, 0)
            result = engine.render("{{ now }}", context)
            assert "2026-04-13" in result

    def test_today_variable(self, engine, context):
        """Test the 'today' built-in variable."""
        with patch('cray.core.template.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 13, 12, 0, 0)
            result = engine.render("{{ today }}", context)
            assert result == "2026-04-13"

    def test_uuid_variable(self, engine, context):
        """Test the 'uuid' built-in variable."""
        result = engine.render("{{ uuid }}", context)
        assert len(result) == 36  # UUID format

    # Filter tests
    def test_upper_filter(self, engine, context):
        """Test the upper filter."""
        result = engine.render("{{ input.name | upper }}", context)
        assert result == "TEST"

    def test_lower_filter(self, engine, context):
        """Test the lower filter."""
        result = engine.render("{{ input.name | lower }}", context)
        assert result == "test"

    def test_default_filter(self, engine, context):
        """Test the default filter for missing values."""
        result = engine.render("{{ input.missing | default('N/A') }}", context)
        assert result == "N/A"

    def test_length_filter(self, engine, context):
        """Test the length filter."""
        result = engine.render("{{ input.items | length }}", context)
        assert result == 3

    def test_join_filter(self, engine, context):
        """Test the join filter."""
        result = engine.render("{{ input.items | join('-') }}", context)
        assert result == "a-b-c"

    def test_int_filter(self, engine, context):
        """Test the int filter."""
        result = engine.render("{{ '42' | int }}", context)
        assert result == 42

    def test_string_filter(self, engine, context):
        """Test the string filter."""
        result = engine.render("{{ 123 | string }}", context)
        assert result == "123"

    # Multiple templates in string
    def test_multiple_templates(self, engine, context):
        """Test multiple templates in one string."""
        result = engine.render(
            "Name: {{ input.name }}, Count: {{ input.count }}",
            context
        )
        assert result == "Name: test, Count: 5"

    # Complex expressions
    def test_array_index(self, engine, context):
        """Test array index access."""
        result = engine.render("{{ input.items[0] }}", context)
        assert result == "a"

    def test_chained_filters(self, engine, context):
        """Test chained filters."""
        result = engine.render("{{ input.name | upper | trim }}", context)
        assert result == "TEST"

    # Literal values
    def test_literal_true(self, engine, context):
        """Test literal true value."""
        result = engine.render("{{ true }}", context)
        assert result is True

    def test_literal_false(self, engine, context):
        """Test literal false value."""
        result = engine.render("{{ false }}", context)
        assert result is False

    def test_literal_null(self, engine, context):
        """Test literal null value."""
        result = engine.render("{{ null }}", context)
        assert result is None

    def test_literal_number(self, engine, context):
        """Test literal number value."""
        result = engine.render("{{ 42 }}", context)
        assert result == 42

    def test_literal_string(self, engine, context):
        """Test literal string value."""
        result = engine.render('{{ "hello" }}', context)
        assert result == "hello"

    # Environment variables
    def test_env_variable(self, engine, context):
        """Test accessing environment variables."""
        env = {"MY_VAR": "test_value"}
        result = engine.render("{{ env.MY_VAR }}", context, env)
        assert result == "test_value"

    def test_env_missing(self, engine, context):
        """Test missing environment variable returns empty string."""
        result = engine.render("{{ env.MISSING }}", context, {})
        assert result == ""

    # Convenience function
    def test_render_function(self, context):
        """Test the convenience render function."""
        result = render("{{ input.name }}", context)
        assert result == "test"


class TestTemplateInWorkflow:
    """Integration tests for templates in workflows."""

    def test_template_in_params(self, tmp_path):
        """Test that templates are rendered in workflow params."""
        from cray.core.workflow import Workflow
        from cray.core.runner import Runner

        # Create a workflow with templates
        workflow_yaml = tmp_path / "test.yaml"
        workflow_yaml.write_text("""
name: template-test
variables:
  prefix: "test_"
  suffix: ".txt"

steps:
  - name: step1
    plugin: shell
    action: exec
    params:
      command: echo "{{ input.message }}"
""")
        
        workflow = Workflow.from_yaml(workflow_yaml)
        runner = Runner()
        
        # Run with input
        task = runner.run_sync(workflow, {"message": "Hello Templates!"})
        
        assert task.status.value == "success"
        assert "Hello Templates!" in task.results[0].output.get("stdout", "")

    def test_variables_merged_with_input(self, tmp_path):
        """Test that variables are merged with input."""
        from cray.core.workflow import Workflow
        from cray.core.runner import Runner

        workflow_yaml = tmp_path / "test.yaml"
        workflow_yaml.write_text("""
name: variable-test
variables:
  base_url: "https://api.example.com"
  timeout: 30

steps:
  - name: echo_vars
    plugin: shell
    action: exec
    params:
      command: echo "URL: {{ input.base_url }}, Timeout: {{ input.timeout }}"
""")
        
        workflow = Workflow.from_yaml(workflow_yaml)
        runner = Runner()
        task = runner.run_sync(workflow)
        
        assert task.status.value == "success"
        assert "https://api.example.com" in task.results[0].output.get("stdout", "")
        assert "30" in task.results[0].output.get("stdout", "")

    def test_step_output_reference(self, tmp_path):
        """Test referencing previous step output."""
        from cray.core.workflow import Workflow
        from cray.core.runner import Runner

        workflow_yaml = tmp_path / "test.yaml"
        workflow_yaml.write_text("""
name: step-reference-test

steps:
  - name: generate
    plugin: shell
    action: exec
    params:
      command: echo "generated_value"

  - name: use_generated
    plugin: shell
    action: exec
    params:
      command: echo "Got: {{ steps.generate.stdout }}"
""")
        
        workflow = Workflow.from_yaml(workflow_yaml)
        runner = Runner()
        task = runner.run_sync(workflow)
        
        assert task.status.value == "success"
        assert "generated_value" in task.results[0].output.get("stdout", "")
