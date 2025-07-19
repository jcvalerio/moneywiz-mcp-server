"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, List
import tempfile
import aiosqlite


@pytest.fixture
def mock_moneywiz_api():
    """Mock MoneywizApi instance for testing."""
    api = Mock()
    
    # Mock account manager
    api.account_manager = Mock()
    api.account_manager.get_all_accounts = Mock(return_value=[
        {
            'id': 'acc1',
            'name': 'Test Checking',
            'type': 'checking',
            'balance': 1500.50,
            'currency': 'USD',
            'hidden': False,
            'created_date': '2024-01-01',
            'institution': 'Test Bank'
        },
        {
            'id': 'acc2', 
            'name': 'Test Savings',
            'type': 'savings',
            'balance': 5000.00,
            'currency': 'USD',
            'hidden': False,
            'created_date': '2024-01-01',
            'institution': 'Test Bank'
        }
    ])
    
    api.account_manager.get_account = Mock(return_value={
        'id': 'acc1',
        'name': 'Test Checking',
        'type': 'checking',
        'balance': 1500.50,
        'currency': 'USD',
        'hidden': False,
        'created_date': '2024-01-01',
        'institution': 'Test Bank'
    })
    
    # Mock transaction manager
    api.transaction_manager = Mock()
    api.transaction_manager.get_transactions_for_account = Mock(return_value=[
        {
            'id': 'txn1',
            'date': '2024-01-15',
            'amount': -25.50,
            'payee': 'Coffee Shop',
            'category': 'Dining'
        }
    ])
    
    return api


@pytest.fixture
async def temp_database():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        db_path = tmp.name
    
    # Create basic tables for testing
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                balance REAL NOT NULL,
                currency TEXT NOT NULL,
                hidden BOOLEAN DEFAULT 0
            )
        """)
        
        await db.execute("""
            CREATE TABLE transactions (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                payee TEXT,
                category TEXT,
                description TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts (id)
            )
        """)
        
        # Insert test data
        await db.execute("""
            INSERT INTO accounts (id, name, type, balance, currency)
            VALUES ('acc1', 'Test Checking', 'checking', 1500.50, 'USD')
        """)
        
        await db.execute("""
            INSERT INTO transactions (id, account_id, date, amount, payee, category)
            VALUES ('txn1', 'acc1', '2024-01-15', -25.50, 'Coffee Shop', 'Dining')
        """)
        
        await db.commit()
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def mock_database_manager(mock_moneywiz_api, temp_database):
    """Mock DatabaseManager for testing."""
    from moneywiz_mcp_server.database.connection import DatabaseManager
    
    manager = Mock(spec=DatabaseManager)
    manager.api = mock_moneywiz_api
    manager.db_path = temp_database
    manager.read_only = True
    
    # Mock async methods
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()
    manager.execute_query = AsyncMock(return_value=[
        {
            'id': 'txn1',
            'date': '2024-01-15',
            'amount': -25.50,
            'payee': 'Coffee Shop',
            'category': 'Dining',
            'account_name': 'Test Checking',
            'currency': 'USD'
        }
    ])
    
    return manager


@pytest.fixture
def sample_account_data() -> List[Dict[str, Any]]:
    """Sample account data for testing."""
    return [
        {
            'id': 'acc1',
            'name': 'Test Checking',
            'type': 'checking',
            'balance': 1500.50,
            'currency': 'USD',
            'hidden': False
        },
        {
            'id': 'acc2',
            'name': 'Test Savings', 
            'type': 'savings',
            'balance': 5000.00,
            'currency': 'USD',
            'hidden': False
        },
        {
            'id': 'acc3',
            'name': 'Hidden Account',
            'type': 'checking',
            'balance': 100.00,
            'currency': 'USD',
            'hidden': True
        }
    ]


@pytest.fixture
def sample_transaction_data() -> List[Dict[str, Any]]:
    """Sample transaction data for testing."""
    return [
        {
            'id': 'txn1',
            'date': '2024-01-15',
            'amount': -25.50,
            'payee': 'Coffee Shop',
            'category': 'Dining',
            'description': 'Morning coffee',
            'account_name': 'Test Checking',
            'currency': 'USD'
        },
        {
            'id': 'txn2',
            'date': '2024-01-14',
            'amount': 2500.00,
            'payee': 'Employer',
            'category': 'Salary',
            'description': 'Monthly salary',
            'account_name': 'Test Checking',
            'currency': 'USD'
        }
    ]