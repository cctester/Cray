# Workflow Reference

Complete reference for Cray workflow YAML syntax.

## Workflow Structure

```yaml
name: workflow-name
version: "1.0"
description: Workflow description

# Optional configuration
config:
  timeout: 300
  retry:
    max_attempts: 3
    delay: 5

# Workflow steps
steps:
  - name: step-name
    plugin: plugin-name
    action: action-name
    params:
      key: value
```

## Top-Level Fields

### `name` (required)

Workflow identifier.

```yaml
name: my-workflow
```

### `version` (optional)

Workflow version. Default: `"1.0"`

```yaml
version: "2.0"
```

### `description` (optional)

Human-readable description.

```yaml
description: Process daily sales report and send email
```

### `config` (optional)

Global configuration.

```yaml
config:
  timeout: 300          # Global timeout in seconds
  retry:                # Default retry policy
    max_attempts: 3
    delay: 5
    backoff: exponential
  continue_on_error: false
```

### `steps` (required)

List of workflow steps.

```yaml
steps:
  - name: step1
    plugin: shell
    action: exec
    params:
      command: echo "Hello"
```

## Step Fields

### `name` (required)

Step identifier. Used to reference step output.

```yaml
steps:
  - name: fetch-data
    plugin: http
    action: get
    params:
      url: https://api.example.com/data
```

Reference in later steps:

```yaml
steps:
  - name: process
    plugin: json
    action: parse
    params:
      data: "{{ steps.fetch-data.body }}"
```

### `plugin` (required)

Plugin name.

```yaml
plugin: shell
plugin: http
plugin: file
plugin: email
plugin: json
plugin: notify
plugin: math
plugin: text
```

### `action` (required)

Action to execute.

```yaml
steps:
  - name: example
    plugin: shell
    action: exec    # Action name
    params:
      command: ls -la
```

### `params` (required)

Action parameters.

```yaml
params:
  url: https://example.com
  timeout: 30
  headers:
    Authorization: Bearer token
```

### `condition` (optional)

Conditional execution.

```yaml
steps:
  - name: send-alert
    plugin: notify
    action: slack
    params:
      webhook_url: "https://hooks.slack.com/..."
      text: "Error occurred"
    condition: "{{ steps.check-status.success == false }}"
```

### `retry` (optional)

Retry configuration for this step.

```yaml
steps:
  - name: unstable-api
    plugin: http
    action: get
    params:
      url: https://unstable-api.example.com
    retry:
      max_attempts: 5
      delay: 10
      backoff: exponential  # or "fixed"
```

### `timeout` (optional)

Step timeout in seconds.

```yaml
steps:
  - name: long-task
    plugin: shell
    action: exec
    params:
      command: ./long-running-script.sh
    timeout: 600  # 10 minutes
```

### `on_error` (optional)

Error handling.

```yaml
steps:
  - name: risky-task
    plugin: shell
    action: exec
    params:
      command: ./risky-script.sh
    on_error: continue  # or "stop" (default)
```

## Variable Substitution

Use `{{ }}` syntax to reference variables.

### Input Variables

```yaml
steps:
  - name: greet
    plugin: shell
    action: exec
    params:
      command: echo "Hello, {{ input.name }}!"
```

Run with input:

```bash
cray run workflow.yaml --input '{"name": "World"}'
```

### Step Output

```yaml
steps:
  - name: fetch
    plugin: http
    action: get
    params:
      url: https://api.example.com/user

  - name: display
    plugin: shell
    action: exec
    params:
      command: echo "User: {{ steps.fetch.body.name }}"
```

### Nested Access

```yaml
steps:
  - name: parse
    plugin: json
    action: query
    params:
      data: "{{ steps.fetch.body }}"
      path: "data.users[0].name"
```

## Built-in Plugins

### shell

Execute shell commands.

```yaml
steps:
  - name: list-files
    plugin: shell
    action: exec
    params:
      command: ls -la
      cwd: /path/to/dir
      env:
        MY_VAR: value
```

### http

Make HTTP requests.

```yaml
steps:
  - name: get-api
    plugin: http
    action: get
    params:
      url: https://api.example.com/data
      headers:
        Authorization: Bearer token
      timeout: 30

  - name: post-api
    plugin: http
    action: post
    params:
      url: https://api.example.com/submit
      body:
        name: test
        value: 123
      headers:
        Content-Type: application/json
```

### file

File operations.

```yaml
steps:
  - name: read-config
    plugin: file
    action: read
    params:
      path: ./config.json

  - name: write-output
    plugin: file
    action: write
    params:
      path: ./output.txt
      content: "{{ steps.process.result }}"

  - name: copy-file
    plugin: file
    action: copy
    params:
      source: ./source.txt
      destination: ./backup/source.txt
```

### email

Send emails.

```yaml
steps:
  - name: send-report
    plugin: email
    action: send
    params:
      to:
        - user@example.com
      subject: Daily Report
      body: "{{ steps.generate-report.content }}"
      smtp_host: smtp.example.com
      smtp_port: 587
      smtp_user: notifications@example.com
      smtp_password: "{{ input.smtp_password }}"
      use_tls: true
```

### json

JSON manipulation.

```yaml
steps:
  - name: parse-data
    plugin: json
    action: parse
    params:
      data: "{{ steps.fetch.body }}"

  - name: query-data
    plugin: json
    action: query
    params:
      data: "{{ steps.parse-data.data }}"
      path: "users[0].name"

  - name: merge-data
    plugin: json
    action: merge
    params:
      objects:
        - "{{ steps.source1.data }}"
        - "{{ steps.source2.data }}"
      deep: true
```

### notify

Send notifications.

```yaml
steps:
  - name: slack-notify
    plugin: notify
    action: slack
    params:
      webhook_url: "https://hooks.slack.com/..."
      text: "Workflow completed!"

  - name: discord-notify
    plugin: notify
    action: discord
    params:
      webhook_url: "https://discord.com/api/webhooks/..."
      content: "Task finished"

  - name: telegram-notify
    plugin: notify
    action: telegram
    params:
      bot_token: "YOUR_BOT_TOKEN"
      chat_id: "YOUR_CHAT_ID"
      text: "<b>Alert!</b> Something happened"
      parse_mode: "HTML"
```

### math

Mathematical operations.

```yaml
steps:
  - name: calculate
    plugin: math
    action: calculate
    params:
      expression: "a + b * c"
      variables:
        a: 10
        b: 5
        c: 2

  - name: format-currency
    plugin: math
    action: format
    params:
      number: 1234.56
      format: currency
      symbol: "$"
```

### text

Text manipulation.

```yaml
steps:
  - name: format-message
    plugin: text
    action: template
    params:
      template: |
        Hello, {{ name }}!
        Your order #{{ order_id }} is ready.
      context:
        name: "{{ steps.get-user.name }}"
        order_id: "{{ steps.get-order.id }}"

  - name: transform
    plugin: text
    action: upper
    params:
      text: "{{ steps.fetch.body }}"
```

## Examples

### Simple Pipeline

```yaml
name: data-pipeline
description: Fetch, process, and save data

steps:
  - name: fetch
    plugin: http
    action: get
    params:
      url: https://api.example.com/data

  - name: transform
    plugin: json
    action: query
    params:
      data: "{{ steps.fetch.body }}"
      path: "results"

  - name: save
    plugin: file
    action: write
    params:
      path: ./data/results.json
      content: "{{ steps.transform.data }}"
```

### Error Handling

```yaml
name: resilient-workflow
description: Workflow with error handling

steps:
  - name: try-api
    plugin: http
    action: get
    params:
      url: https://api.example.com/data
    retry:
      max_attempts: 3
      delay: 5
    on_error: continue

  - name: check-result
    plugin: shell
    action: exec
    params:
      command: echo "{{ steps.try-api.success }}"
    condition: "{{ steps.try-api.success == true }}"

  - name: fallback
    plugin: file
    action: read
    params:
      path: ./cache/data.json
    condition: "{{ steps.try-api.success == false }}"
```

### Parallel Steps

```yaml
name: parallel-fetch
description: Fetch multiple sources in parallel

steps:
  - name: fetch-users
    plugin: http
    action: get
    params:
      url: https://api.example.com/users

  - name: fetch-products
    plugin: http
    action: get
    params:
      url: https://api.example.com/products

  - name: fetch-orders
    plugin: http
    action: get
    params:
      url: https://api.example.com/orders

  - name: combine
    plugin: json
    action: merge
    params:
      objects:
        - users: "{{ steps.fetch-users.body }}"
        - products: "{{ steps.fetch-products.body }}"
        - orders: "{{ steps.fetch-orders.body }}"
```

## Best Practices

1. **Use descriptive names** - Make step names meaningful
2. **Keep steps focused** - One responsibility per step
3. **Handle errors** - Use `retry` and `on_error` appropriately
4. **Document workflows** - Add descriptions
5. **Use variables** - Avoid hardcoding values
6. **Test incrementally** - Build and test step by step
7. **Set timeouts** - Prevent hanging workflows
