""" Database plugin using pydtc for universal database connectivity.

Supports:
- MySQL, PostgreSQL, Oracle, SQL Server
- Hive (with Kerberos auth)
- SQLite
- Any JDBC-compatible database

Security notes:
- Table/schema names are quoted as SQL identifiers to prevent injection.
- User-provided values should use parameterized queries via the `query` action.
"""

import asyncio
from typing import Dict, Any, Optional, List
from loguru import logger

from cray.plugins import Plugin


class DatabasePlugin(Plugin):
    """Database operations using pydtc."""

    name = "database"
    description = "Database operations for MySQL, PostgreSQL, Oracle, Hive, and more"
    version = "1.0.0"

    @property
    def actions(self):
        return {
            "connect": {"description": "Connect to database", "params": [
                {"name": "db_type", "type": "string", "required": True, "description": "Database type"},
                {"name": "host", "type": "string", "required": True, "description": "Database host"},
            ]},
            "disconnect": {"description": "Disconnect from database", "params": [
                {"name": "connection_name", "type": "string", "required": True, "description": "Connection name"},
            ]},
            "query": {"description": "Execute query", "params": [
                {"name": "db_type", "type": "string", "required": True, "description": "Database type"},
                {"name": "sql", "type": "string", "required": True, "description": "SQL query"},
            ]},
            "insert": {"description": "Insert data", "params": [
                {"name": "table", "type": "string", "required": True, "description": "Table name"},
                {"name": "data", "type": "object", "required": True, "description": "Data to insert"},
            ]},
            "load_temp": {"description": "Load to table", "params": [
                {"name": "db_type", "type": "string", "required": True, "description": "Database type"},
                {"name": "table", "type": "string", "required": True, "description": "Table name"},
                {"name": "data", "type": "array", "required": True, "description": "Data to load"},
            ]},
        }

    def __init__(self):
        self._connections: Dict[str, Any] = {}
        self._pydtc = None

    def _get_pydtc(self):
        """Lazy load pydtc."""
        if self._pydtc is None:
            try:
                import pydtc
                self._pydtc = pydtc
            except ImportError:
                raise ImportError(
                    "pydtc is required for database plugin. "
                    "Install with: pip install pydtc"
                )
        return self._pydtc

    @staticmethod
    def _quote_identifier(name: str) -> str:
        """Quote a SQL identifier to prevent injection.

        Validates that the identifier contains only safe characters
        (alphanumeric, underscore, dot) and wraps it in double-quotes.
        """
        # Strip whitespace
        name = name.strip()
        if not name:
            raise ValueError("Empty identifier")
        # Validate characters: allow alphanumeric, underscore, dot, hyphen
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.\-]*$', name):
            raise ValueError(
                f"Invalid SQL identifier: {name!r}. "
                f"Only alphanumeric, underscore, dot, and hyphen characters allowed."
            )
        # Double-quote the identifier (standard SQL quoting)
        return f'"{name}"'

    async def execute(
        self, action: str, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Any:
        """Execute a database action."""
        actions = {
            "connect": self._connect,
            "disconnect": self._disconnect,
            "query": self._query,
            "insert": self._insert,
            "update": self._update,
            "delete": self._delete,
            "execute": self._execute_raw,
            "load_temp": self._load_temp,
            "read_sql": self._read_sql,
            "list_tables": self._list_tables,
            "describe_table": self._describe_table,
        }
        if action not in actions:
            return {"error": f"Unknown action: {action}"}
        return await actions[action](params, context)

    async def _connect(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Connect to a database."""
        pydtc = self._get_pydtc()
        db_type = params.get("db_type", "mysql")
        host = params.get("host", "localhost")
        port = params.get("port")
        database = params.get("database", "")
        user = params.get("user", "")
        password = params.get("password", "")
        conn_name = params.get("connection_name", "default")
        options = params.get("options", {})

        try:
            loop = asyncio.get_running_loop()
            conn = await loop.run_in_executor(
                None,
                lambda: pydtc.connect(db_type, host, user, password, database, **options)
            )
            self._connections[conn_name] = {
                "connection": conn,
                "type": db_type,
                "host": host,
                "database": database,
            }
            logger.info(f"Connected to {db_type} database: {host}/{database}")
            return {
                "success": True,
                "connection": conn_name,
                "type": db_type,
                "host": host,
                "database": database,
            }
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return {"success": False, "error": str(e)}

    async def _disconnect(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Disconnect from a database."""
        conn_name = params.get("connection_name", "default")
        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}

        try:
            conn_info = self._connections.pop(conn_name)
            conn_info["connection"].close()
            logger.info(f"Disconnected: {conn_name}")
            return {"success": True, "connection": conn_name}
        except Exception as e:
            logger.error(f"Failed to disconnect: {e}")
            return {"success": False, "error": str(e)}

    async def _query(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a SELECT query."""
        sql = params.get("sql", "")
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}

        conn = self._connections[conn_name]["connection"]

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: conn.execute(sql)
            )

            # Convert result to list of dicts
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = result.fetchall()
            data = [dict(zip(columns, row)) for row in rows]

            return {
                "success": True,
                "data": data,
                "columns": columns,
                "row_count": len(data),
            }
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {"success": False, "error": str(e)}

    async def _insert(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Insert data into a table."""
        table = params.get("table", "")
        data = params.get("data", {})
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}
        if not table or not data:
            return {"success": False, "error": "Missing required parameters: table, data"}

        conn = self._connections[conn_name]["connection"]

        # Build parameterized INSERT
        quoted_table = self._quote_identifier(table)
        columns = list(data.keys())
        quoted_cols = ", ".join(self._quote_identifier(c) for c in columns)
        placeholders = ", ".join([":{}".format(i + 1) for i in range(len(columns))])
        values = [data[c] for c in columns]

        sql = f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES ({placeholders})"

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, lambda: conn.execute(sql, values)
            )
            return {"success": True, "table": table, "rows_affected": 1}
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            return {"success": False, "error": str(e)}

    async def _update(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update data in a table."""
        table = params.get("table", "")
        data = params.get("data", {})
        where = params.get("where", "")
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}
        if not table or not data or not where:
            return {"success": False, "error": "Missing required parameters: table, data, where"}

        conn = self._connections[conn_name]["connection"]

        quoted_table = self._quote_identifier(table)
        set_clause = ", ".join(
            f"{self._quote_identifier(k)} = :set_{i}"
            for i, k in enumerate(data.keys())
        )
        sql = f"UPDATE {quoted_table} SET {set_clause} WHERE {where}"

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: conn.execute(sql, list(data.values()))
            )
            return {"success": True, "rows_affected": result.rowcount}
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return {"success": False, "error": str(e)}

    async def _delete(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Delete data from a table."""
        table = params.get("table", "")
        where = params.get("where", "")
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}
        if not table or not where:
            return {"success": False, "error": "Missing required parameters: table, where"}

        conn = self._connections[conn_name]["connection"]

        quoted_table = self._quote_identifier(table)
        sql = f"DELETE FROM {quoted_table} WHERE {where}"

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: conn.execute(sql)
            )
            return {"success": True, "rows_affected": result.rowcount}
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_raw(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute raw SQL (DDL, etc.)."""
        sql = params.get("sql", "")
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}
        if not sql:
            return {"success": False, "error": "Missing required parameter: sql"}

        conn = self._connections[conn_name]["connection"]

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: conn.execute(sql)
            )
            rowcount = result.rowcount if hasattr(result, "rowcount") else -1
            return {"success": True, "rows_affected": rowcount}
        except Exception as e:
            logger.error(f"Execute failed: {e}")
            return {"success": False, "error": str(e)}

    async def _load_temp(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Load data into a temporary table (fast batch load)."""
        data = params.get("data", [])
        table = params.get("table", "")
        conn_name = params.get("connection_name", "default")
        create = params.get("create", True)

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}
        if not data:
            return {"success": False, "error": "No data to load"}

        pydtc = self._get_pydtc()
        conn = self._connections[conn_name]["connection"]

        try:
            import pandas as pd
            df = pd.DataFrame(data)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, lambda: pydtc.load_temp(df, table, conn, create=create)
            )
            return {
                "success": True,
                "rows_loaded": len(data),
                "table": table,
            }
        except Exception as e:
            logger.error(f"Load temp failed: {e}")
            return {"success": False, "error": str(e)}

    async def _read_sql(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Read SQL query results into DataFrame."""
        return await self._query(params, context)

    async def _list_tables(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """List tables in the database."""
        conn_name = params.get("connection_name", "default")
        schema = params.get("schema")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}

        conn_info = self._connections[conn_name]
        db_type = conn_info["type"]

        # Database-specific queries — use quoted identifiers for schema
        table_queries = {
            "mysql": "SHOW TABLES",
            "postgresql": "SELECT tablename FROM pg_tables WHERE schemaname = 'public'",
            "oracle": "SELECT table_name FROM user_tables",
            "sqlite": "SELECT name FROM sqlite_master WHERE type='table'",
        }

        sql = table_queries.get(db_type, "SHOW TABLES")

        if schema and db_type == "postgresql":
            # Use quoted identifier instead of f-string injection
            quoted_schema = self._quote_identifier(schema)
            sql = f"SELECT tablename FROM pg_tables WHERE schemaname = {quoted_schema}"

        params["sql"] = sql
        return await self._query(params, context)

    async def _describe_table(
        self, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Describe table structure."""
        table = params.get("table", "")
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}
        if not table:
            return {"success": False, "error": "Missing required parameter: table"}

        conn_info = self._connections[conn_name]
        db_type = conn_info["type"]

        # Quote table name to prevent injection
        quoted_table = self._quote_identifier(table)

        # Database-specific describe queries — use quoted identifiers
        describe_queries = {
            "mysql": f"DESCRIBE {quoted_table}",
            "postgresql": f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = {quoted_table}",
            "oracle": f"SELECT column_name, data_type FROM user_tab_columns WHERE table_name = {quoted_table}",
            "sqlite": f"PRAGMA table_info({quoted_table})",
        }

        sql = describe_queries.get(db_type, f"DESCRIBE {quoted_table}")
        params["sql"] = sql
        return await self._query(params, context)

    def teardown(self) -> None:
        """Close all connections."""
        for conn_name, conn_info in list(self._connections.items()):
            try:
                conn_info["connection"].close()
                logger.debug(f"Closed connection: {conn_name}")
            except Exception as e:
                logger.warning(f"Error closing connection {conn_name}: {e}")
        self._connections.clear()
