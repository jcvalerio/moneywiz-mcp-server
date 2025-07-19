"""Unit tests for database connection management."""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import tempfile

from moneywiz_mcp_server.database.connection import DatabaseManager


class TestDatabaseManager:
    """Test cases for DatabaseManager class."""
    
    @pytest.mark.unit
    def test_init_with_default_read_only(self):
        """Test DatabaseManager initialization with default read-only mode."""
        db_path = "/test/path/database.sqlite"
        manager = DatabaseManager(db_path)
        
        assert manager.db_path == Path(db_path)
        assert manager.read_only is True
        assert manager._api is None
        assert manager._connection is None
    
    @pytest.mark.unit
    def test_init_with_read_write_mode(self):
        """Test DatabaseManager initialization with read-write mode."""
        db_path = "/test/path/database.sqlite"
        manager = DatabaseManager(db_path, read_only=False)
        
        assert manager.db_path == Path(db_path)
        assert manager.read_only is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialize_read_only_mode(self, temp_database):
        """Test database initialization in read-only mode."""
        with patch('moneywiz_mcp_server.database.connection.MoneywizApi') as mock_api_class, \
             patch('moneywiz_mcp_server.database.connection.aiosqlite.connect', new_callable=AsyncMock) as mock_connect:
            
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_connection = AsyncMock()
            mock_connect.return_value = mock_connection
            
            manager = DatabaseManager(temp_database, read_only=True)
            await manager.initialize()
            
            # Verify MoneywizApi was initialized with correct path
            mock_api_class.assert_called_once_with(temp_database)
            assert manager._api == mock_api
            
            # Verify SQLite connection was made with read-only URI
            expected_uri = f"file:{temp_database}?mode=ro"
            mock_connect.assert_called_once_with(expected_uri, uri=True)
            assert manager._connection == mock_connection
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialize_read_write_mode(self, temp_database):
        """Test database initialization in read-write mode."""
        with patch('moneywiz_mcp_server.database.connection.MoneywizApi') as mock_api_class, \
             patch('moneywiz_mcp_server.database.connection.aiosqlite.connect', new_callable=AsyncMock) as mock_connect:
            
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_connection = AsyncMock()
            mock_connect.return_value = mock_connection
            
            manager = DatabaseManager(temp_database, read_only=False)
            await manager.initialize()
            
            # Verify SQLite connection was made without read-only flag
            mock_connect.assert_called_once_with(temp_database, uri=True)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_connection(self):
        """Test closing database connections."""
        manager = DatabaseManager("/test/path")
        mock_connection = AsyncMock()
        manager._connection = mock_connection
        
        await manager.close()
        
        mock_connection.close.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_no_connection(self):
        """Test closing when no connection exists."""
        manager = DatabaseManager("/test/path")
        
        # Should not raise any exception
        await manager.close()
    
    @pytest.mark.unit
    def test_api_property_initialized(self):
        """Test api property when initialized."""
        manager = DatabaseManager("/test/path")
        mock_api = Mock()
        manager._api = mock_api
        
        assert manager.api == mock_api
    
    @pytest.mark.unit
    def test_api_property_not_initialized(self):
        """Test api property when not initialized."""
        manager = DatabaseManager("/test/path")
        
        with pytest.raises(RuntimeError, match="Database not initialized"):
            _ = manager.api
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_transaction_context_read_only_error(self):
        """Test transaction context in read-only mode should raise error."""
        manager = DatabaseManager("/test/path", read_only=True)
        
        with pytest.raises(RuntimeError, match="Cannot start transaction in read-only mode"):
            async with manager.transaction():
                pass
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_transaction_context_success(self):
        """Test successful transaction context."""
        manager = DatabaseManager("/test/path", read_only=False)
        mock_connection = AsyncMock()
        manager._connection = mock_connection
        
        async with manager.transaction() as conn:
            assert conn == mock_connection
        
        mock_connection.execute.assert_called_once_with("BEGIN")
        mock_connection.commit.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_transaction_context_rollback_on_exception(self):
        """Test transaction rollback on exception."""
        manager = DatabaseManager("/test/path", read_only=False)
        mock_connection = AsyncMock()
        manager._connection = mock_connection
        
        with pytest.raises(Exception, match="Test error"):
            async with manager.transaction():
                raise Exception("Test error")
        
        mock_connection.rollback.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_query_success(self):
        """Test successful query execution."""
        manager = DatabaseManager("/test/path")
        mock_connection = AsyncMock()
        manager._connection = mock_connection
        
        # Mock cursor behavior
        mock_cursor = AsyncMock()
        mock_cursor.description = [("id",), ("name",), ("balance",)]
        mock_cursor.fetchall.return_value = [
            ("acc1", "Test Account", 1000.0),
            ("acc2", "Another Account", 2000.0)
        ]
        
        mock_connection.execute.return_value = mock_cursor
        
        query = "SELECT id, name, balance FROM accounts"
        params = ("param1",)
        
        result = await manager.execute_query(query, params)
        
        expected = [
            {"id": "acc1", "name": "Test Account", "balance": 1000.0},
            {"id": "acc2", "name": "Another Account", "balance": 2000.0}
        ]
        
        assert result == expected
        mock_connection.execute.assert_called_once_with(query, params)
        mock_cursor.close.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_query_no_params(self):
        """Test query execution without parameters."""
        manager = DatabaseManager("/test/path")
        mock_connection = AsyncMock()
        manager._connection = mock_connection
        
        # Mock cursor behavior
        mock_cursor = AsyncMock()
        mock_cursor.description = [("count",)]
        mock_cursor.fetchall.return_value = [(5,)]
        
        mock_connection.execute.return_value = mock_cursor
        
        query = "SELECT COUNT(*) as count FROM accounts"
        
        result = await manager.execute_query(query)
        
        expected = [{"count": 5}]
        assert result == expected
        mock_connection.execute.assert_called_once_with(query, ())
        mock_cursor.close.assert_called_once()