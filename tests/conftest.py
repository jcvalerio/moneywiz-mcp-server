"""Pytest configuration and shared fixtures."""

from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import AsyncMock, Mock

import aiosqlite
import pytest


@pytest.fixture
def mock_moneywiz_api():
    """Mock MoneywizApi instance for testing."""
    api = Mock()

    # Mock account manager
    api.account_manager = Mock()
    api.account_manager.get_all_accounts = Mock(
        return_value=[
            {
                "id": "acc1",
                "name": "Test Checking",
                "type": "checking",
                "balance": 1500.50,
                "currency": "USD",
                "hidden": False,
                "created_date": "2024-01-01",
                "institution": "Test Bank",
            },
            {
                "id": "acc2",
                "name": "Test Savings",
                "type": "savings",
                "balance": 5000.00,
                "currency": "USD",
                "hidden": False,
                "created_date": "2024-01-01",
                "institution": "Test Bank",
            },
        ]
    )

    api.account_manager.get_account = Mock(
        return_value={
            "id": "acc1",
            "name": "Test Checking",
            "type": "checking",
            "balance": 1500.50,
            "currency": "USD",
            "hidden": False,
            "created_date": "2024-01-01",
            "institution": "Test Bank",
        }
    )

    # Mock transaction manager
    api.transaction_manager = Mock()
    api.transaction_manager.get_transactions_for_account = Mock(
        return_value=[
            {
                "id": "txn1",
                "date": "2024-01-15",
                "amount": -25.50,
                "payee": "Coffee Shop",
                "category": "Dining",
            }
        ]
    )

    return api


@pytest.fixture
async def temp_database():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    # Create basic tables for testing
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                balance REAL NOT NULL,
                currency TEXT NOT NULL,
                hidden BOOLEAN DEFAULT 0
            )
        """
        )

        await db.execute(
            """
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
        """
        )

        # Insert test data
        await db.execute(
            """
            INSERT INTO accounts (id, name, type, balance, currency)
            VALUES ('acc1', 'Test Checking', 'checking', 1500.50, 'USD')
        """
        )

        await db.execute(
            """
            INSERT INTO transactions (id, account_id, date, amount, payee, category)
            VALUES ('txn1', 'acc1', '2024-01-15', -25.50, 'Coffee Shop', 'Dining')
        """
        )

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

    # Create a sophisticated mock that returns different data based on query
    async def mock_execute_query(query: str, params=None):
        """Mock execute_query that returns appropriate data based on the query."""
        if "Z_PRIMARYKEY" in query and "Z_ENT" in query:
            # Entity type mapping query
            return [
                {"Z_ENT": 10, "Z_NAME": "BankCheque"},  # Checking account
                {"Z_ENT": 11, "Z_NAME": "BankSaving"},  # Savings account
                {"Z_ENT": 12, "Z_NAME": "Cash"},
                {"Z_ENT": 13, "Z_NAME": "CreditCard"},
            ]
        elif "ZOPENINGBALANCE" in query and "Z_PK" in query:
            # Balance query for specific account
            if params:
                account_id = params[0]
                if account_id == 1:
                    return [{"ZOPENINGBALANCE": 1000.0}]
                elif account_id == 2:
                    return [{"ZOPENINGBALANCE": 5000.0}]
            return [{"ZOPENINGBALANCE": 0.0}]
        elif "ZAMOUNT1" in query and "ZACCOUNT2" in query:
            # Transaction amounts query for balance calculation
            if params:
                account_id = params[0]
                if account_id == 1:
                    return [{"ZAMOUNT1": 500.0}, {"ZAMOUNT1": -25.50}]  # Net +474.50
                elif account_id == 2:
                    return [{"ZAMOUNT1": 100.0}]  # Net +100.0
            return []
        elif "ZSYNCOBJECT" in query and "Z_ENT" in query and params:
            # Account data query - return different accounts based on entity type
            entity_id = params[0]
            if entity_id == 10:  # BankCheque - for checking account (comes first)
                return [
                    {
                        "Z_PK": 1,
                        "Z_ENT": 10,
                        "ZNAME": "Test Checking",
                        "ZGID": "acc1",
                        "ZACCOUNTTYPEIDENTIFIER": "checking",
                        "ZOPENINGBALANCE": 1000.0,
                        "ZISHIDDEN": 0,
                        "ZCURRENCY": "USD",
                        "ZCURRENCYNAME": "USD",
                        "ZINSTITUTIONNAME": "Test Bank",
                    }
                ]
            elif entity_id == 11:  # BankSaving - for savings account (comes second)
                return [
                    {
                        "Z_PK": 2,
                        "Z_ENT": 11,
                        "ZNAME": "Test Savings",
                        "ZGID": "acc2",
                        "ZACCOUNTTYPEIDENTIFIER": "savings",
                        "ZOPENINGBALANCE": 5000.0,
                        "ZISHIDDEN": 0,
                        "ZCURRENCY": "USD",
                        "ZCURRENCYNAME": "USD",
                        "ZINSTITUTIONNAME": "Test Bank",
                    }
                ]
            else:
                # Other entity types return empty to avoid duplication
                return []
        else:
            # Default empty result
            return []

    manager.execute_query = AsyncMock(side_effect=mock_execute_query)

    return manager


@pytest.fixture
def sample_account_data() -> list[dict[str, Any]]:
    """Sample account data for testing."""
    return [
        {
            "id": "acc1",
            "name": "Test Checking",
            "type": "checking",
            "balance": 1500.50,
            "currency": "USD",
            "hidden": False,
        },
        {
            "id": "acc2",
            "name": "Test Savings",
            "type": "savings",
            "balance": 5000.00,
            "currency": "USD",
            "hidden": False,
        },
        {
            "id": "acc3",
            "name": "Hidden Account",
            "type": "checking",
            "balance": 100.00,
            "currency": "USD",
            "hidden": True,
        },
    ]


@pytest.fixture
def sample_transaction_data() -> list[dict[str, Any]]:
    """Sample transaction data for testing."""
    return [
        {
            "id": "txn1",
            "date": "2024-01-15",
            "amount": -25.50,
            "payee": "Coffee Shop",
            "category": "Dining",
            "description": "Morning coffee",
            "account_name": "Test Checking",
            "currency": "USD",
        },
        {
            "id": "txn2",
            "date": "2024-01-14",
            "amount": 2500.00,
            "payee": "Employer",
            "category": "Salary",
            "description": "Monthly salary",
            "account_name": "Test Checking",
            "currency": "USD",
        },
    ]
