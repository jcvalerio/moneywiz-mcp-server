"""Unit tests for account-related MCP tools."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from moneywiz_mcp_server.tools.accounts import list_accounts_tool, get_account_tool


class TestListAccountsTool:
    """Test cases for list_accounts tool."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_accounts_basic(self, mock_database_manager, sample_account_data):
        """Test basic account listing (excludes hidden by default)."""
        # Setup mock
        mock_database_manager.api.account_manager.get_all_accounts.return_value = sample_account_data
        
        # Create tool and get handler
        tool = list_accounts_tool(mock_database_manager)
        result = await tool.handler()
        
        # Verify results - should exclude hidden accounts by default
        assert len(result) == 2  # Only non-hidden accounts
        assert result[0]['name'] == 'Test Checking'
        assert result[1]['name'] == 'Test Savings'
        # Hidden Account should not be included
        assert all(account['name'] != 'Hidden Account' for account in result)
        
        # Verify all accounts have required fields
        for account in result:
            assert 'id' in account
            assert 'name' in account
            assert 'type' in account
            assert 'balance' in account
            assert 'currency' in account
            assert 'last_updated' in account
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_accounts_exclude_hidden(self, mock_database_manager, sample_account_data):
        """Test account listing excluding hidden accounts."""
        mock_database_manager.api.account_manager.get_all_accounts.return_value = sample_account_data
        
        tool = list_accounts_tool(mock_database_manager)
        result = await tool.handler(include_hidden=False)
        
        # Should only return non-hidden accounts
        assert len(result) == 2
        assert all(account['name'] != 'Hidden Account' for account in result)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_accounts_include_hidden(self, mock_database_manager, sample_account_data):
        """Test account listing including hidden accounts."""
        mock_database_manager.api.account_manager.get_all_accounts.return_value = sample_account_data
        
        tool = list_accounts_tool(mock_database_manager)
        result = await tool.handler(include_hidden=True)
        
        # Should return all accounts
        assert len(result) == 3
        assert any(account['name'] == 'Hidden Account' for account in result)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_accounts_filter_by_type(self, mock_database_manager, sample_account_data):
        """Test account listing filtered by type."""
        mock_database_manager.api.account_manager.get_all_accounts.return_value = sample_account_data
        
        tool = list_accounts_tool(mock_database_manager)
        result = await tool.handler(account_type='checking')
        
        # Should only return non-hidden checking accounts by default
        assert len(result) == 1  # Only Test Checking (Hidden Account excluded by default)
        assert all(account['type'] == 'checking' for account in result)
        assert result[0]['name'] == 'Test Checking'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_accounts_empty_result(self, mock_database_manager):
        """Test account listing with no accounts."""
        mock_database_manager.api.account_manager.get_all_accounts.return_value = []
        
        tool = list_accounts_tool(mock_database_manager)
        result = await tool.handler()
        
        assert result == []
    
    @pytest.mark.unit
    def test_list_accounts_tool_properties(self, mock_database_manager):
        """Test tool properties and parameters."""
        tool = list_accounts_tool(mock_database_manager)
        
        assert tool.name == "list_accounts"
        assert "List all MoneyWiz accounts" in tool.description
        
        # Check parameters structure
        params = tool.inputSchema
        assert params["type"] == "object"
        assert "include_hidden" in params["properties"]
        assert "account_type" in params["properties"]
        
        # Check parameter defaults and types
        include_hidden_param = params["properties"]["include_hidden"]
        assert include_hidden_param["type"] == "boolean"
        assert include_hidden_param["default"] is False


class TestGetAccountTool:
    """Test cases for get_account tool."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_account_basic(self, mock_database_manager):
        """Test basic account retrieval."""
        account_data = {
            'id': 'acc1',
            'name': 'Test Checking',
            'type': 'checking',
            'balance': 1500.50,
            'currency': 'USD',
            'created_date': '2024-01-01',
            'institution': 'Test Bank'
        }
        
        mock_database_manager.api.account_manager.get_account.return_value = account_data
        
        tool = get_account_tool(mock_database_manager)
        result = await tool.handler(account_id="acc1")
        
        # Verify result structure
        assert result['id'] == 'acc1'
        assert result['name'] == 'Test Checking'
        assert result['type'] == 'checking'
        assert 'balance' in result
        assert result['currency'] == 'USD'
        assert result['created_date'] == '2024-01-01'
        assert result['institution'] == 'Test Bank'
        
        # Should not include transactions by default
        assert 'recent_transactions' not in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_account_with_transactions(self, mock_database_manager):
        """Test account retrieval with transactions."""
        account_data = {
            'id': 'acc1',
            'name': 'Test Checking',
            'type': 'checking',
            'balance': 1500.50,
            'currency': 'USD',
            'created_date': '2024-01-01',
            'institution': 'Test Bank'
        }
        
        transaction_data = [
            {
                'id': 'txn1',
                'date': '2024-01-15',
                'amount': -25.50,
                'payee': 'Coffee Shop',
                'category': 'Dining'
            }
        ]
        
        mock_database_manager.api.account_manager.get_account.return_value = account_data
        mock_database_manager.api.transaction_manager.get_transactions_for_account.return_value = transaction_data
        
        tool = get_account_tool(mock_database_manager)
        result = await tool.handler(account_id="acc1", include_transactions=True)
        
        # Should include transactions
        assert 'recent_transactions' in result
        assert len(result['recent_transactions']) == 1
        
        transaction = result['recent_transactions'][0]
        assert transaction['id'] == 'txn1'
        assert transaction['date'] == '2024-01-15'
        assert 'amount' in transaction  # Should be formatted
        assert transaction['payee'] == 'Coffee Shop'
        assert transaction['category'] == 'Dining'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_account_not_found(self, mock_database_manager):
        """Test account retrieval for non-existent account."""
        mock_database_manager.api.account_manager.get_account.return_value = None
        
        tool = get_account_tool(mock_database_manager)
        
        with pytest.raises(ValueError, match="Account .* not found"):
            await tool.handler(account_id="nonexistent")
    
    @pytest.mark.unit
    def test_get_account_tool_properties(self, mock_database_manager):
        """Test tool properties and parameters."""
        tool = get_account_tool(mock_database_manager)
        
        assert tool.name == "get_account"
        assert "detailed information about a specific account" in tool.description
        
        # Check parameters structure
        params = tool.inputSchema
        assert params["type"] == "object"
        assert "account_id" in params["properties"]
        assert "include_transactions" in params["properties"]
        assert "account_id" in params["required"]
        
        # Check parameter types
        account_id_param = params["properties"]["account_id"]
        assert account_id_param["type"] == "string"
        
        include_txn_param = params["properties"]["include_transactions"]
        assert include_txn_param["type"] == "boolean"
        assert include_txn_param["default"] is False