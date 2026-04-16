# Database Plugin

Database plugin for Cray, powered by [pydtc](https://github.com/cctester/pydtc) for universal database connectivity.

## Features

- **Universal Connectivity**: Connect to MySQL, PostgreSQL, Oracle, SQL Server, Hive, SQLite, and any JDBC-compatible database
- **Kerberos Support**: Hive with Kerberos authentication
- **Fast Batch Load**: Efficient temporary table creation and data loading
- **Async Operations**: Non-blocking database operations
- **Connection Pooling**: Manage multiple database connections

## Installation

```bash
pip install cray[database]
```

Or install pydtc directly:

```bash
pip install pydtc pandas
```

## Supported Databases

| Database | Type | Default Port |
|----------|------|--------------|
| MySQL | `mysql` | 3306 |
| PostgreSQL | `postgresql` | 5432 |
| Oracle | `oracle` | 1521 |
| SQL Server | `sqlserver` | 1433 |
| Hive | `hive` | 10000 |
| SQLite | `sqlite` | - |

## Actions

### connect

Connect to a database.

```yaml
- name: connect-db
  plugin: database
  action: connect
  params:
    db_type: mysql
    host: localhost
    port: 3306
    database: mydb
    user: root
    password: secret
    connection_name: mydb
```

### disconnect

Disconnect from a database.

```yaml
- name: disconnect
  plugin: database
  action: disconnect
  params:
    connection_name: mydb
```

### query

Execute a SELECT query.

```yaml
- name: get-users
  plugin: database
  action: query
  params:
    connection_name: mydb
    sql: "SELECT * FROM users WHERE active = true"
```

Returns:
```json
{
  "success": true,
  "data": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
  "row_count": 2
}
```

### insert

Insert data into a table.

```yaml
- name: insert-user
  plugin: database
  action: insert
  params:
    connection_name: mydb
    table: users
    data:
      name: Alice
      email: alice@example.com
```

Or insert multiple rows:

```yaml
- name: insert-users
  plugin: database
  action: insert
  params:
    connection_name: mydb
    table: users
    data:
      - name: Alice
        email: alice@example.com
      - name: Bob
        email: bob@example.com
```

### update

Execute an UPDATE statement.

```yaml
- name: update-user
  plugin: database
  action: update
  params:
    connection_name: mydb
    sql: "UPDATE users SET active = false WHERE last_login < '2024-01-01'"
```

### delete

Execute a DELETE statement.

```yaml
- name: delete-inactive
  plugin: database
  action: delete
  params:
    connection_name: mydb
    sql: "DELETE FROM users WHERE active = false"
```

### execute

Execute raw SQL.

```yaml
- name: create-table
  plugin: database
  action: execute
  params:
    connection_name: mydb
    sql: |
      CREATE TABLE IF NOT EXISTS logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
```

### load_temp

Load data into a temporary table (fast batch load).

```yaml
- name: load-data
  plugin: database
  action: load_temp
  params:
    connection_name: mydb
    table: temp_data
    data:
      - id: 1
        value: "A"
      - id: 2
        value: "B"
    create: true  # Create table if not exists
```

### list_tables

List tables in the database.

```yaml
- name: list-tables
  plugin: database
  action: list_tables
  params:
    connection_name: mydb
    schema: public  # Optional, for PostgreSQL
```

### describe_table

Get table structure.

```yaml
- name: describe-users
  plugin: database
  action: describe_table
  params:
    connection_name: mydb
    table: users
```

## Complete Example

```yaml
name: etl-pipeline
description: ETL pipeline using database plugin

steps:
  # Connect to source database
  - name: connect-source
    plugin: database
    action: connect
    params:
      db_type: mysql
      host: source-db.example.com
      database: production
      user: reader
      password: ${SOURCE_DB_PASSWORD}
      connection_name: source

  # Connect to target database
  - name: connect-target
    plugin: database
    action: connect
    params:
      db_type: postgresql
      host: target-db.example.com
      database: warehouse
      user: writer
      password: ${TARGET_DB_PASSWORD}
      connection_name: target

  # Extract data
  - name: extract
    plugin: database
    action: query
    params:
      connection_name: source
      sql: "SELECT * FROM orders WHERE date >= CURDATE() - INTERVAL 1 DAY"

  # Transform and load
  - name: load
    plugin: database
    action: load_temp
    params:
      connection_name: target
      table: staging_orders
      data: ${extract.data}
      create: true

  # Run transformation
  - name: transform
    plugin: database
    action: execute
    params:
      connection_name: target
      sql: |
        INSERT INTO fact_orders
        SELECT * FROM staging_orders
        ON CONFLICT (id) DO UPDATE SET
          amount = EXCLUDED.amount,
          updated_at = NOW()

  # Cleanup
  - name: disconnect-all
    plugin: database
    action: disconnect
    params:
      connection_name: source

  - name: disconnect-target
    plugin: database
    action: disconnect
    params:
      connection_name: target
```

## Using with Hive (Kerberos)

```yaml
- name: connect-hive
  plugin: database
  action: connect
  params:
    db_type: hive
    host: hive-server.example.com
    port: 10000
    database: default
    user: hive
    password: ""
    connection_name: hive_conn
    options:
      kerberos: true
      principal: "hive/_HOST@EXAMPLE.COM"
```

## Environment Variables

Use environment variables for sensitive data:

```yaml
params:
  password: ${DB_PASSWORD}
```

Set the environment variable:

```bash
export DB_PASSWORD=your_secret_password
cray run workflow.yaml
```

## Error Handling

All actions return a consistent response format:

```json
{
  "success": true,
  // ... action-specific data
}
```

On error:

```json
{
  "success": false,
  "error": "Connection refused"
}
```

## pydtc Features

This plugin leverages pydtc's powerful features:

- **JDBC Connectivity**: Universal database access via JDBC drivers
- **Fast Batch Load**: Efficient bulk data loading
- **CLOB/BLOB Handling**: Convert CLOB to string, save BLOB to file
- **Multiprocessing**: Parallel processing for large datasets
- **Retry Logic**: Built-in retry for transient failures

For more information, see [pydtc documentation](https://github.com/cctester/pydtc).
