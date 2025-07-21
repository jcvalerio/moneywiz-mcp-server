"""Database connection management for MoneyWiz SQLite database."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Any

try:
    from moneywiz_api import MoneywizApi
except ImportError:
    # For testing without moneywiz-api installed
    MoneywizApi = None

import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages connections to MoneyWiz SQLite database.

    This class provides a high-level interface for accessing MoneyWiz data
    through both the moneywiz-api library and direct SQLite queries.
    """

    def __init__(self, db_path: str, read_only: bool = True) -> None:
        """Initialize DatabaseManager.

        Args:
            db_path: Path to MoneyWiz SQLite database file
            read_only: Whether to open database in read-only mode (default: True)
        """
        self.db_path = Path(db_path)
        self.read_only = read_only
        self._api: Any | None = None  # MoneywizApi instance
        self._connection: aiosqlite.Connection | None = None

        logger.info(
            f"DatabaseManager initialized for {db_path} (read_only={read_only})"
        )

    async def initialize(self) -> None:
        """Initialize database connections.

        This method sets up both the moneywiz-api interface and async SQLite
        connection for direct queries.

        Raises:
            ImportError: If moneywiz-api is not installed
            sqlite3.Error: If database connection fails
        """
        logger.info("Initializing database connections...")

        # Initialize moneywiz-api (optional - will fallback to direct SQLite
        # if not available)
        if MoneywizApi is None:
            logger.warning(
                "moneywiz-api library not found. Using direct SQLite access only."
            )
            self._api = None
        else:
            try:
                # MoneywizApi expects a Path object, not a string
                self._api = MoneywizApi(self.db_path)
                logger.debug("MoneywizApi initialized successfully")
            except Exception as e:
                # Log the full error details for debugging
                logger.warning(
                    f"Failed to initialize MoneywizApi: {type(e).__name__}: {e!s}"
                )
                logger.info("Continuing with direct SQLite access only")
                logger.info(
                    "This may be due to database schema changes in the latest "
                    "MoneyWiz version"
                )
                self._api = None

        # Initialize async SQLite connection
        try:
            if self.read_only:
                # Use read-only URI for safety
                uri = f"file:{self.db_path}?mode=ro"
                self._connection = await aiosqlite.connect(uri, uri=True)
            else:
                self._connection = await aiosqlite.connect(str(self.db_path), uri=True)

            # Configure connection for better performance
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute(
                "PRAGMA query_only = ON"
                if self.read_only
                else "PRAGMA query_only = OFF"
            )

            logger.debug("Async SQLite connection established")
        except Exception as e:
            logger.error(f"Failed to establish SQLite connection: {e}")
            raise

        logger.info("Database connections initialized successfully")

    async def close(self) -> None:
        """Close database connections.

        This method cleanly closes all open database connections.
        """
        logger.info("Closing database connections...")

        if self._connection:
            try:
                await self._connection.close()
                logger.debug("SQLite connection closed")
            except Exception as e:
                logger.warning(f"Error closing SQLite connection: {e}")
            finally:
                self._connection = None

        # Note: moneywiz-api doesn't require explicit cleanup
        self._api = None

        logger.info("Database connections closed")

    @property
    def api(self) -> Any:
        """Get MoneywizApi instance.

        Returns:
            MoneywizApi instance for high-level database operations

        Raises:
            RuntimeError: If database not initialized or moneywiz-api unavailable
        """
        if self._api is None:
            raise RuntimeError(
                "MoneywizApi not available. Using direct SQLite access only."
            )
        return self._api

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Context manager for database transactions.

        This method provides transaction support for write operations.
        Automatically handles commit/rollback based on success/failure.

        Yields:
            aiosqlite.Connection: Database connection within transaction

        Raises:
            RuntimeError: If database is in read-only mode

        Example:
            async with db_manager.transaction() as conn:
                await conn.execute("INSERT INTO accounts ...")
        """
        if self.read_only:
            raise RuntimeError("Cannot start transaction in read-only mode")

        if not self._connection:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        logger.debug("Starting database transaction")

        try:
            await self._connection.execute("BEGIN")
            yield self._connection
            await self._connection.commit()
            logger.debug("Transaction committed successfully")
        except Exception as e:
            await self._connection.rollback()
            logger.warning(f"Transaction rolled back due to error: {e}")
            raise

    async def execute_query(
        self, query: str, params: tuple | None = None
    ) -> list[dict[str, Any]]:
        """Execute a SELECT query and return results as dictionaries.

        Args:
            query: SQL SELECT query to execute
            params: Optional query parameters

        Returns:
            List of dictionaries representing query results

        Raises:
            RuntimeError: If database not initialized
            sqlite3.Error: If query execution fails

        Example:
            results = await db_manager.execute_query(
                "SELECT * FROM accounts WHERE type = ?",
                ("checking",)
            )
        """
        if not self._connection:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        logger.debug(
            f"Executing query: {query[:100]}{'...' if len(query) > 100 else ''}"
        )

        try:
            cursor = await self._connection.execute(query, params or ())

            # Get column names from cursor description
            columns = [description[0] for description in cursor.description]

            # Fetch all rows and convert to dictionaries
            rows = await cursor.fetchall()
            result = [dict(zip(columns, row, strict=False)) for row in rows]

            await cursor.close()

            logger.debug(f"Query returned {len(result)} rows")
            return result

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
