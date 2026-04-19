"""
Database plugin using pydtc for universal database connectivity.

Supports:
- MySQL, PostgreSQL, Oracle, SQL Server
- Hive (with Kerberos auth)
- SQLite
- Any JDBC-compatible database
"""

import asyncio
from typing import Dict, Any, Optional, List
from loguru import logger

from cray.plugins import Plugin


class DatabasePlugin(Plugin):
    """Database operations using pydtc."""

class DatabasePlugin(Plugin):
    name = "database"
    description = "Database operations for MySQL, PostgreSQL, Oracle, Hive, and more"
    version = "1.0.0"
    
    @property
    def actions(self):
        return {
            "connect": {"description": "Connect to database", "params": [{"name": "db_type", "type": "string", "required": True, "description": "Database type"}, {"name": "host", "type": "string", "required": True, "description": "Database host"}]},
            "disconnect": {"description": "Disconnect from database", "params": [{"name": "connection_name", "type": "string", "required": True, "description": "Connection name"}]},
            "query": {"description": "Execute query", "params": [{"name": "db_type", "type": "string", "required": True, "description": "Database type"}, {"name": "sql", "type": "string", "required": True, "description": "SQL query"}]},
            "insert": {"description": "Insert data", "params": [{"name": "table", "type": "string", "required": True, "description": "Table name"}, {"name": "data", "type": "object", "required": True, "description": "Data to insert"}]},
            "load_temp": {"description": "Load to table", "params": [{"name": "db_type", "type": "string", "required": True, "description": "Database type"}, {"name": "table", "type": "string", "required": True, "description": "Table name"}, {"name": "data", "type": "array", "required": True, "description": "Data to load"}]},
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

    async def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
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
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Connect to a database.

        Params:
            db_type: Database type (mysql, postgresql, oracle, hive, etc.)
            host: Database host
            port: Database port (optional)
            database: Database name
            user: Username
            password: Password
            connection_name: Name for this connection (default: 'default')
            options: Additional connection options

        Returns:
            Connection info
        """
        pydtc = self._get_pydtc()

        db_type = params.get("db_type", "mysql")
        host = params.get("host", "localhost")
        port = params.get("port")
        database = params.get("database", "")
        user = params.get("user", "")
        password = params.get("password", "")
        conn_name = params.get("connection_name", "default")
        options = params.get("options", {})

        # Build connection string
        conn_str = f"{db_type}://{user}:{password}@{host}"
        if port:
            conn_str += f":{port}"
        if database:
            conn_str += f"/{database}"

        try:
            # Run in thread pool since pydtc is synchronous
            loop = asyncio.get_event_loop()
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
                "connection_name": conn_name,
                "type": db_type,
                "host": host,
                "database": database,
            }

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return {"success": False, "error": str(e)}

    async def _disconnect(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Disconnect from database."""
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}

        try:
            conn_info = self._connections[conn_name]
            conn = conn_info["connection"]

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, conn.close)

            del self._connections[conn_name]
            logger.info(f"Disconnected from '{conn_name}'")

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _query(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a SELECT query.

        Params:
            sql: SQL query
            connection_name: Connection name (default: 'default')
            params: Query parameters (optional)

        Returns:
            Query results as list of dicts
        """
        sql = params.get("sql", "")
        conn_name = params.get("connection_name", "default")
        query_params = params.get("params", {})

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}

        pydtc = self._get_pydtc()
        conn = self._connections[conn_name]["connection"]

        try:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: pydtc.read_sql(sql, conn)
            )

            # Convert DataFrame to dict
            if df is not None:
                result = df.to_dict(orient="records")
                return {
                    "success": True,
                    "data": result,
                    "row_count": len(result),
                }
            else:
                return {"success": True, "data": [], "row_count": 0}

        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {"success": False, "error": str(e)}

    async def _insert(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Insert data into a table.

        Params:
            table: Table name
            data: Data to insert (dict or list of dicts)
            connection_name: Connection name

        Returns:
            Insert result
        """
        table = params.get("table", "")
        data = params.get("data", [])
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}

        if not table:
            return {"success": False, "error": "Table name required"}

        if isinstance(data, dict):
            data = [data]

        if not data:
            return {"success": False, "error": "No data to insert"}

        pydtc = self._get_pydtc()
        conn = self._connections[conn_name]["connection"]

        try:
            import pandas as pd
            df = pd.DataFrame(data)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: pydtc.load_temp(df, table, conn, create=False)
            )

            return {
                "success": True,
                "rows_inserted": len(data),
                "table": table,
            }

        except Exception as e:
            logger.error(f"Insert failed: {e}")
            return {"success": False, "error": str(e)}

    async def _update(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute an UPDATE statement.

        Params:
            sql: UPDATE SQL statement
            connection_name: Connection name

        Returns:
            Update result
        """
        return await self._execute_raw(params, context)

    async def _delete(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a DELETE statement.

        Params:
            sql: DELETE SQL statement
            connection_name: Connection name

        Returns:
            Delete result
        """
        return await self._execute_raw(params, context)

    async def _execute_raw(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute raw SQL.

        Params:
            sql: SQL statement
            connection_name: Connection name

        Returns:
            Execution result
        """
        sql = params.get("sql", "")
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}

        conn = self._connections[conn_name]["connection"]

        try:
            loop = asyncio.get_event_loop()

            # Get cursor and execute
            cursor = conn.cursor()
            await loop.run_in_executor(None, lambda: cursor.execute(sql))
            conn.commit()

            rowcount = cursor.rowcount
            cursor.close()

            return {
                "success": True,
                "rows_affected": rowcount,
            }

        except Exception as e:
            logger.error(f"Execute failed: {e}")
            return {"success": False, "error": str(e)}

    async def _load_temp(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Load data into a temporary table (fast batch load).

        Params:
            data: Data to load (list of dicts)
            table: Table name
            connection_name: Connection name
            create: Create table if not exists (default: True)

        Returns:
            Load result
        """
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

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: pydtc.load_temp(df, table, conn, create=create)
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
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Read SQL query results into DataFrame.

        Params:
            sql: SQL query
            connection_name: Connection name

        Returns:
            Query results
        """
        return await self._query(params, context)

    async def _list_tables(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        List tables in the database.

        Params:
            connection_name: Connection name
            schema: Schema name (optional)

        Returns:
            List of tables
        """
        conn_name = params.get("connection_name", "default")
        schema = params.get("schema")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}

        conn_info = self._connections[conn_name]
        db_type = conn_info["type"]

        # Database-specific queries
        table_queries = {
            "mysql": "SHOW TABLES",
            "postgresql": "SELECT tablename FROM pg_tables WHERE schemaname = 'public'",
            "oracle": "SELECT table_name FROM user_tables",
            "sqlite": "SELECT name FROM sqlite_master WHERE type='table'",
        }

        sql = table_queries.get(db_type, "SHOW TABLES")

        if schema and db_type == "postgresql":
            sql = f"SELECT tablename FROM pg_tables WHERE schemaname = '{schema}'"

        params["sql"] = sql
        return await self._query(params, context)

    async def _describe_table(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Describe table structure.

        Params:
            table: Table name
            connection_name: Connection name

        Returns:
            Table structure
        """
        table = params.get("table", "")
        conn_name = params.get("connection_name", "default")

        if conn_name not in self._connections:
            return {"success": False, "error": f"Connection '{conn_name}' not found"}

        conn_info = self._connections[conn_name]
        db_type = conn_info["type"]

        # Database-specific describe queries
        describe_queries = {
            "mysql": f"DESCRIBE {table}",
            "postgresql": f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'",
            "oracle": f"SELECT column_name, data_type FROM user_tab_columns WHERE table_name = '{table.upper()}'",
            "sqlite": f"PRAGMA table_info({table})",
        }

        sql = describe_queries.get(db_type, f"DESCRIBE {table}")

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
