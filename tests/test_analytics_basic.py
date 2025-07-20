"""Basic tests for analytics functionality."""

from datetime import datetime, timedelta
import os
import sys
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from moneywiz_mcp_server.models.transaction import TransactionModel, TransactionType
from moneywiz_mcp_server.services.transaction_service import TransactionService
from moneywiz_mcp_server.utils.date_utils import (
    get_date_range_from_months,
    parse_natural_language_date,
)


def test_date_range_from_months():
    """Test date range generation from months."""
    date_range = get_date_range_from_months(3)

    # Should be approximately 3 months ago
    expected_start = datetime.now() - timedelta(days=90)
    assert abs((date_range.start_date - expected_start).days) <= 1

    # End date should be now
    assert abs((date_range.end_date - datetime.now()).total_seconds()) < 60


def test_parse_natural_language_date():
    """Test natural language date parsing."""
    # Test "last 3 months"
    date_range = parse_natural_language_date("last 3 months")
    expected_start = datetime.now() - timedelta(days=90)
    assert abs((date_range.start_date - expected_start).days) <= 1

    # Test "this year"
    date_range = parse_natural_language_date("this year")
    current_year = datetime.now().year
    assert date_range.start_date.year == current_year
    assert date_range.start_date.month == 1
    assert date_range.start_date.day == 1


def test_transaction_model_from_raw_data():
    """Test TransactionModel creation from raw data."""
    raw_data = {
        "Z_PK": 123,
        "Z_ENT": 37,  # DepositTransaction
        "ZACCOUNT2": 456,
        "ZAMOUNT1": -50.00,
        "ZDATE1": 0,  # Core Data epoch
        "ZDESC2": "Test Transaction",
        "ZNOTES1": "Test notes",
        "ZRECONCILED": 1,
        "ZCATEGORY2": 789,
        "ZPAYEE2": 101,
        "ZORIGINALCURRENCY": "USD",
        "ZORIGINALAMOUNT": -50.00,
    }

    transaction = TransactionModel.from_raw_data(raw_data)

    assert transaction.id == "123"
    assert transaction.entity_id == 37
    assert transaction.transaction_type == TransactionType.DEPOSIT
    assert transaction.account_id == 456
    assert float(transaction.amount) == -50.00
    assert transaction.description == "Test Transaction"
    assert transaction.notes == "Test notes"
    assert transaction.reconciled is True
    assert transaction.category_id == 789
    assert transaction.payee_id == 101


def test_transaction_expense_income_classification():
    """Test transaction expense/income classification."""
    # Test expense (negative amount)
    expense_data = {
        "Z_PK": 1,
        "Z_ENT": 37,
        "ZACCOUNT2": 1,
        "ZAMOUNT1": -100.00,
        "ZDATE1": 0,
        "ZDESC2": "Expense",
        "ZRECONCILED": 0,
    }
    expense = TransactionModel.from_raw_data(expense_data)
    assert expense.is_expense()
    assert not expense.is_income()

    # Test income (positive amount)
    income_data = {
        "Z_PK": 2,
        "Z_ENT": 37,
        "ZACCOUNT2": 1,
        "ZAMOUNT1": 100.00,
        "ZDATE1": 0,
        "ZDESC2": "Income",
        "ZRECONCILED": 0,
    }
    income = TransactionModel.from_raw_data(income_data)
    assert income.is_income()
    assert not income.is_expense()


@pytest.mark.asyncio()
async def test_transaction_service_initialization():
    """Test TransactionService initialization."""
    mock_db = Mock()
    service = TransactionService(mock_db)

    assert service.db_manager == mock_db
    assert isinstance(service._category_cache, dict)
    assert isinstance(service._payee_cache, dict)
    assert isinstance(service._account_currency_cache, dict)


@pytest.mark.asyncio()
async def test_transaction_service_get_transactions():
    """Test TransactionService get_transactions method."""
    # Mock database manager
    mock_db = AsyncMock()
    mock_db.execute_query.return_value = [
        {
            "Z_PK": 1,
            "Z_ENT": 37,
            "ZACCOUNT2": 123,
            "ZAMOUNT1": -50.00,
            "ZDATE1": 0,
            "ZDESC2": "Test Transaction",
            "ZRECONCILED": 0,
            "ZCATEGORY2": None,
            "ZPAYEE2": None,
        }
    ]

    service = TransactionService(mock_db)

    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    transactions = await service.get_transactions(start_date, end_date)

    assert len(transactions) == 1
    assert transactions[0].id == "1"
    assert transactions[0].description == "Test Transaction"
    assert mock_db.execute_query.called


if __name__ == "__main__":
    # Run basic tests
    test_date_range_from_months()
    test_parse_natural_language_date()
    test_transaction_model_from_raw_data()
    test_transaction_expense_income_classification()
    print("✅ All basic tests passed!")
