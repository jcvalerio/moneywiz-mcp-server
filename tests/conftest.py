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
def temp_database():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    # Create basic tables for testing using sqlite3 (sync)
    import sqlite3

    with sqlite3.connect(db_path) as db:
        db.execute(
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

        db.execute(
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
        db.execute(
            """
            INSERT INTO accounts (id, name, type, balance, currency)
            VALUES ('acc1', 'Test Checking', 'checking', 1500.50, 'USD')
        """
        )

        db.execute(
            """
            INSERT INTO transactions (id, account_id, date, amount, payee, category)
            VALUES ('txn1', 'acc1', '2024-01-15', -25.50, 'Coffee Shop', 'Dining')
        """
        )

        db.commit()

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
            # Entity type mapping query - using the exact names expected by accounts.py
            return [
                {"Z_ENT": 10, "Z_NAME": "BankChequeAccount"},  # Checking account
                {"Z_ENT": 11, "Z_NAME": "BankSavingAccount"},  # Savings account
                {"Z_ENT": 12, "Z_NAME": "CashAccount"},
                {"Z_ENT": 13, "Z_NAME": "CreditCardAccount"},
            ]
        elif "ZOPENINGBALANCE" in query and "Z_PK" in query:
            # Balance query for specific account
            if params:
                account_id = params[0]
                balance_map = {
                    1: [{"ZOPENINGBALANCE": 1000.0}],
                    2: [{"ZOPENINGBALANCE": 5000.0}],
                    3: [{"ZOPENINGBALANCE": 100.0}],
                }
                return balance_map.get(account_id, [{"ZOPENINGBALANCE": 0.0}])
            return [{"ZOPENINGBALANCE": 0.0}]
        elif "ZAMOUNT1" in query and "ZACCOUNT2" in query:
            # Transaction amounts query for balance calculation
            if params:
                account_id = params[0]
                transaction_map = {
                    1: [{"ZAMOUNT1": 500.0}, {"ZAMOUNT1": -25.50}],  # Net +474.50
                    2: [{"ZAMOUNT1": 100.0}],  # Net +100.0
                    3: [
                        {"ZAMOUNT1": 0.0}
                    ],  # Net 0.0 (balance stays at opening balance)
                }
                return transaction_map.get(account_id, [])
            return []
        elif "ZSYNCOBJECT" in query and "Z_ENT" in query and params:
            # Account data query - could be list query or get specific account query
            if len(params) == 1:
                # List accounts query (entity_id only)
                entity_id = params[0]
            elif len(params) == 3:
                # Get specific account query (entity_id, account_id, pk_value)
                entity_id, account_id, pk_value = params
                # Return specific account based on account_id
                if entity_id == 10 and (account_id == "acc1" or pk_value == 1):
                    return [
                        {
                            "Z_PK": 1,
                            "Z_ENT": 10,
                            "ZNAME": "Test Checking",
                            "ZGID": "acc1",
                            "ZACCOUNTTYPEIDENTIFIER": "checking",
                            "ZOPENINGBALANCE": 1000.0,
                            "ZARCHIVED": 0,
                            "ZCURRENCY": "USD",
                            "ZCURRENCYNAME": "USD",
                            "ZINSTITUTIONNAME": "Test Bank",
                            "ZOBJECTCREATIONDATE": "2024-01-01",
                            "ZBANKWEBSITEURL": "Test Bank",
                            "ZINFO": "Test account info",
                            "ZLASTFOURDIGITS": "1234",
                        }
                    ]
                elif entity_id == 11 and (account_id == "acc2" or pk_value == 2):
                    return [
                        {
                            "Z_PK": 2,
                            "Z_ENT": 11,
                            "ZNAME": "Test Savings",
                            "ZGID": "acc2",
                            "ZACCOUNTTYPEIDENTIFIER": "savings",
                            "ZOPENINGBALANCE": 5000.0,
                            "ZARCHIVED": 0,
                            "ZCURRENCY": "USD",
                            "ZCURRENCYNAME": "USD",
                            "ZINSTITUTIONNAME": "Test Bank",
                            "ZOBJECTCREATIONDATE": "2024-01-01",
                            "ZBANKWEBSITEURL": "Test Bank",
                            "ZINFO": "Test savings account",
                            "ZLASTFOURDIGITS": "5678",
                        }
                    ]
                else:
                    return []  # Account not found
            elif len(params) == 2:
                # Get specific account query by ZGID only (entity_id, account_id)
                entity_id, account_id = params
                # Same logic as above but without pk_value
                if entity_id == 10 and account_id == "acc1":
                    return [
                        {
                            "Z_PK": 1,
                            "Z_ENT": 10,
                            "ZNAME": "Test Checking",
                            "ZGID": "acc1",
                            "ZACCOUNTTYPEIDENTIFIER": "checking",
                            "ZOPENINGBALANCE": 1000.0,
                            "ZARCHIVED": 0,
                            "ZCURRENCY": "USD",
                            "ZCURRENCYNAME": "USD",
                            "ZINSTITUTIONNAME": "Test Bank",
                            "ZOBJECTCREATIONDATE": "2024-01-01",
                            "ZBANKWEBSITEURL": "Test Bank",
                            "ZINFO": "Test account info",
                            "ZLASTFOURDIGITS": "1234",
                        }
                    ]
                elif entity_id == 11 and account_id == "acc2":
                    return [
                        {
                            "Z_PK": 2,
                            "Z_ENT": 11,
                            "ZNAME": "Test Savings",
                            "ZGID": "acc2",
                            "ZACCOUNTTYPEIDENTIFIER": "savings",
                            "ZOPENINGBALANCE": 5000.0,
                            "ZARCHIVED": 0,
                            "ZCURRENCY": "USD",
                            "ZCURRENCYNAME": "USD",
                            "ZINSTITUTIONNAME": "Test Bank",
                            "ZOBJECTCREATIONDATE": "2024-01-01",
                            "ZBANKWEBSITEURL": "Test Bank",
                            "ZINFO": "Test savings account",
                            "ZLASTFOURDIGITS": "5678",
                        }
                    ]
                else:
                    return []  # Account not found

            # List accounts query (original logic)
            entity_id = params[0]
            if entity_id == 10:  # BankCheque - for checking accounts
                return [
                    {
                        "Z_PK": 1,
                        "Z_ENT": 10,
                        "ZNAME": "Test Checking",
                        "ZGID": "acc1",
                        "ZACCOUNTTYPEIDENTIFIER": "checking",
                        "ZOPENINGBALANCE": 1000.0,
                        "ZARCHIVED": 0,  # Use ZARCHIVED instead of ZISHIDDEN
                        "ZCURRENCY": "USD",
                        "ZCURRENCYNAME": "USD",
                        "ZINSTITUTIONNAME": "Test Bank",
                    },
                    {
                        "Z_PK": 3,
                        "Z_ENT": 10,
                        "ZNAME": "Hidden Account",
                        "ZGID": "acc3",
                        "ZACCOUNTTYPEIDENTIFIER": "checking",
                        "ZOPENINGBALANCE": 100.0,
                        "ZARCHIVED": 1,  # This account is hidden/archived
                        "ZCURRENCY": "USD",
                        "ZCURRENCYNAME": "USD",
                        "ZINSTITUTIONNAME": "Test Bank",
                    },
                ]
            elif entity_id == 11:  # BankSaving - for savings account
                return [
                    {
                        "Z_PK": 2,
                        "Z_ENT": 11,
                        "ZNAME": "Test Savings",
                        "ZGID": "acc2",
                        "ZACCOUNTTYPEIDENTIFIER": "savings",
                        "ZOPENINGBALANCE": 5000.0,
                        "ZARCHIVED": 0,
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
