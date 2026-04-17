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
| **database** | `connect`, `disconnect`, `query`, `insert`, `update`, `delete`, `execute`, `load_temp`, `list_tables`, `describe_table` | Database operations (MySQL, PostgreSQL, Oracle, Hive, SQLite) |
| **git** | `clone`, `init`, `status`, `add`, `rm`, `commit`, `push`, `pull`, `fetch`, `branch`, `checkout`, `merge`, `tag`, `log`, `diff`, `remote`, `reset`, `stash`, `config` | Git repository operations |

## Use Cases

### 📊 Data Processing Pipelines

Build ETL (Extract, Transform, Load) workflows to move data between systems:

```yaml
name: daily-etl
description: Extract data from MySQL, transform, load to PostgreSQL

steps:
  - name: extract
    plugin: database
    action: query
    params:
      db_type: mysql
      host: source-db.example.com
      sql: "SELECT * FROM orders WHERE date = CURDATE()"

  - name: transform
    plugin: json
    action: transform
    params:
      data: "{{ steps.extract.data }}"
      operations:
        - operation: map
          field: amount
          expr: "float(x) * 1.1"  # Add 10% markup

  - name: load
    plugin: database
    action: load_temp
    params:
      db_type: postgresql
      host: warehouse.example.com
      table: staging_orders
      data: "{{ steps.transform.result }}"
```

### 🔧 DevOps Automation

Automate routine operations and monitoring:

```yaml
name: server-health-check
description: Check server health and alert on issues

steps:
  - name: check-disk
    plugin: shell
    action: exec
    params:
      command: df -h / | tail -1 | awk '{print $5}' | tr -d '%'

  - name: check-memory
    plugin: shell
    action: exec
    params:
      command: free | grep Mem | awk '{printf "%.1f", $3/$2 * 100}'

  - name: alert-if-needed
    plugin: notify
    action: slack
    params:
      webhook: ${SLACK_WEBHOOK}
      message: |
        ⚠️ Server Alert
        Disk: {{ steps.check-disk.stdout }}%
        Memory: {{ steps.check-memory.stdout }}%
      condition: "{{ steps.check-disk.stdout | int > 80 or steps.check-memory.stdout | float > 90 }}"
```

### 🔗 API Integration

Connect multiple APIs and aggregate data:

```yaml
name: api-aggregation
description: Fetch data from multiple APIs and combine

steps:
  - name: get-users
    plugin: http
    action: get
    params:
      url: https://api.example.com/users

  - name: get-orders
    plugin: http
    action: get
    params:
      url: https://api.example.com/orders

  - name: combine-data
    plugin: json
    action: merge
    params:
      sources:
        - "{{ steps.get-users.body }}"
        - "{{ steps.get-orders.body }}"

  - name: save-report
    plugin: file
    action: write
    params:
      path: ./reports/daily-{{ input.date }}.json
      content: "{{ steps.combine-data.result | tojson }}"
```

### 📧 Automated Reporting

Generate and distribute reports on schedule:

```yaml
name: weekly-report
description: Generate weekly report and email to stakeholders

triggers:
  - schedule: "0 9 * * 1"  # Monday 9 AM

steps:
  - name: query-sales
    plugin: database
    action: query
    params:
      connection_name: analytics
      sql: |
        SELECT product, SUM(quantity) as units, SUM(revenue) as total
        FROM sales
        WHERE week = LAST_WEEK()
        GROUP BY product

  - name: format-report
    plugin: text
    action: template
    params:
      template: |
        # Weekly Sales Report

        Total Products: {{ steps.query-sales.row_count }}

        {% for row in steps.query-sales.data %}
        - {{ row.product }}: {{ row.units }} units, ${{ row.total }}
        {% endfor %}

  - name: send-email
    plugin: email
    action: send
    params:
      to: team@company.com
      subject: "Weekly Sales Report - {{ input.date }}"
      body: "{{ steps.format-report.result }}"
```

### 🤖 CI/CD Auxiliary Tasks

Support deployment pipelines with notifications and cleanup:

```yaml
name: post-deploy
description: Post-deployment tasks

steps:
  - name: notify-deploy
    plugin: notify
    action: discord
    params:
      webhook: ${DISCORD_WEBHOOK}
      message: "🚀 Deployment {{ input.version }} completed on {{ input.env }}"

  - name: run-migrations
    plugin: database
    action: execute
    params:
      connection_name: app-db
      sql: "UPDATE schema_version SET version = '{{ input.version }}'"

  - name: cleanup-old-backups
    plugin: shell
    action: exec
    params:
      command: find /backups -type f -mtime +30 -delete

  - name: health-check
    plugin: http
    action: get
    params:
      url: https://{{ input.env }}.example.com/health
      expected_status: 200
```

### 📁 File Processing

Batch process files with transformations:

```yaml
name: process-csv-files
description: Process uploaded CSV files

steps:
  - name: list-files
    plugin: file
    action: list
    params:
      path: ./uploads
      pattern: "*.csv"

  - name: process-each
    plugin: shell
    action: script
    params:
      script: |
        for file in {{ steps.list-files.files | join(' ') }}; do
          python process.py "$file" --output ./processed/
        done

  - name: archive-originals
    plugin: file
    action: copy
    params:
      src: ./uploads
      dst: ./archive/{{ input.date }}
```

### 🔔 Monitoring & Alerting

Monitor systems and send alerts:

```yaml
name: website-monitor
description: Monitor website uptime

triggers:
  - interval: 300  # Every 5 minutes

steps:
  - name: check-site
    plugin: http
    action: get
    params:
      url: https://mywebsite.com
      timeout: 10

  - name: alert-on-failure
    plugin: notify
    action: telegram
    params:
      bot_token: ${TELEGRAM_BOT}
      chat_id: ${TELEGRAM_CHAT}
      message: "🚨 Website check failed: {{ steps.check-site.error }}"
      condition: "{{ not steps.check-site.success }}"

  - name: log-status
    plugin: file
    action: write
    params:
      path: ./logs/uptime.log
      content: "{{ input.time }} - {{ steps.check-site.status_code }}"
      mode: append
```

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

## Roadmap

### 🚧 In Progress

- [ ] **Dashboard Frontend** - Vue 3 web UI for workflow management (partially implemented)
- [ ] **WebSocket Real-time Updates** - Live task status in dashboard
- [ ] **Workflow Editor** - Visual workflow builder in dashboard

### 📋 Planned Plugins

| Plugin | Description | Priority |
|--------|-------------|----------|
| ~~**database**~~ | SQLite, PostgreSQL, MySQL, Oracle, Hive | ✅ Done |
| ~~**git**~~ | Git clone, commit, push, pull, branch, tag | ✅ Done |
| **aws** | AWS S3, EC2, Lambda integrations | High |
| **docker** | Docker container management | Medium |
| **redis** | Redis cache and queue operations | Medium |
| **csv** | CSV file read, write, transform | Medium |
| **xml** | XML parsing and transformation | Medium |
| **image** | Image resize, convert, watermark | Low |
| **pdf** | PDF generation and manipulation | Low |
| **archive** | Zip, tar, gzip compression | Low |
| **ssh** | Remote SSH command execution | Medium |
| **ftp** | FTP/SFTP file transfers | Low |

### 🔮 Planned Features

- [ ] **Workflow Dependencies** - Chain workflows with dependencies
- [ ] **Parallel Execution** - Run multiple steps concurrently
- [ ] **Error Handling** - `on_error` steps, retry policies
- [ ] **Variables & Templates** - Jinja2 templates in workflows
- [ ] **Secrets Management** - Secure credential storage
- [ ] **Workflow Versioning** - Track and rollback changes
- [ ] **Import/Export** - Share workflows between instances
- [ ] **Plugin Marketplace** - Discover and install community plugins
- [ ] **Metrics & Monitoring** - Prometheus integration
- [ ] **Cluster Mode** - Distributed workflow execution

## Contributing

Contributions are welcome! See [PLUGIN_DEVELOPMENT.md](docs/PLUGIN_DEVELOPMENT.md) for plugin development guide.

## License

MIT
