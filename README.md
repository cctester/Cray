# Cray 🦞

A lightweight automation tool with claws.

## Features

- 📝 **YAML Workflows** - Define automation tasks in simple YAML files
- 🔌 **Plugin System** - Extensible plugin architecture
- ⚡ **Async Execution** - Fast async/await based execution
- 📊 **Rich CLI** - Beautiful command line interface
- 🌐 **Web API** - REST API with FastAPI
- ⏰ **Scheduling** - Cron-based and interval scheduling
- 💾 **Storage** - JSON-based task persistence
- 🔧 **Built-in Plugins** - Shell, HTTP, File operations included

## Installation

```bash
# Basic installation
pip install cray

# With web support
pip install cray[web]

# With scheduling support
pip install cray[schedule]

# Everything
pip install cray[all]
```

## Quick Start

### Create a workflow

```yaml
# hello.yaml
name: hello-world
description: A simple Hello World workflow

steps:
  - name: greet
    plugin: shell
    action: exec
    params:
      command: echo "Hello from Cray! 🦞"
```

### Run it

```bash
cray run hello.yaml
```

## CLI Commands

```bash
# Run a workflow
cray run workflow.yaml

# Validate a workflow
cray validate workflow.yaml

# Create a new workflow template
cray create my-workflow

# List available plugins
cray list --plugins

# Schedule a workflow
cray schedule add workflow.yaml --cron "0 9 * * *"
cray schedule add workflow.yaml --interval 3600

# List scheduled workflows
cray schedule list

# Remove a scheduled workflow
cray schedule remove <job_id>

# Start web API server
cray serve --port 8000
```

## Web API

Start the server:

```bash
cray serve --host 0.0.0.0 --port 8000
```

API Endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/workflows` | GET, POST | List/create workflows |
| `/workflows/{name}` | GET, DELETE | Get/delete workflow |
| `/workflows/{name}/run` | POST | Run a workflow |
| `/tasks` | GET | List recent tasks |
| `/tasks/{id}` | GET | Get task details |
| `/plugins` | GET | List plugins |

API Documentation: http://localhost:8000/docs

## Built-in Plugins

| Plugin | Actions | Description |
|--------|---------|-------------|
| **shell** | `exec`, `script` | Execute shell commands |
| **http** | `get`, `post`, `put`, `delete` | Make HTTP requests |
| **file** | `read`, `write`, `copy`, `move`, `delete`, `list`, `exists`, `mkdir` | File operations |
| **email** | `send`, `send_template` | Send emails via SMTP |
| **json** | `parse`, `stringify`, `query`, `merge`, `transform` | JSON manipulation |
| **notify** | `slack`, `discord`, `telegram`, `webhook`, `desktop` | Send notifications |
| **math** | `calculate`, `sum`, `average`, `min`, `max`, `round`, `random`, `format` | Math operations |
| **text** | `format`, `replace`, `regex`, `split`, `join`, `upper`, `lower`, `capitalize`, `trim`, `template` | Text manipulation |

## Workflow Reference

### Basic Structure

```yaml
name: my-workflow
version: "1.0"
description: Workflow description

triggers:
  - schedule: "0 9 * * *"  # Daily at 9 AM

steps:
  - name: step-name
    plugin: plugin-name
    action: action-name
    params:
      key: value
    condition: "{{ steps.previous_step.success }}"
    retry: 3
    timeout: 300
```

### Conditions

Use `{{ }}` templates to reference previous step outputs:

```yaml
steps:
  - name: fetch
    plugin: http
    action: get
    params:
      url: https://api.example.com/data

  - name: process
    plugin: file
    action: write
    params:
      path: ./output.json
      content: "{{ steps.fetch.body }}"
    condition: "{{ steps.fetch.success }}"
```

### Scheduled Workflows

```yaml
name: daily-backup
description: Daily backup workflow

triggers:
  - schedule: "0 2 * * *"  # Run at 2 AM

steps:
  - name: backup
    plugin: file
    action: copy
    params:
      src: ./data
      dst: ./backups/{{ input.date }}
```

## Development

```bash
# Clone the repo
git clone https://github.com/yourusername/cray.git
cd cray

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=cray
```

## License

MIT
