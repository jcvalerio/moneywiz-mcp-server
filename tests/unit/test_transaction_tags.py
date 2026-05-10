"""Unit tests for transaction tag resolution."""

from unittest.mock import AsyncMock

import pytest

from moneywiz_mcp_server.models.transaction import TransactionModel
from moneywiz_mcp_server.services.transaction_service import TransactionService


@pytest.mark.asyncio
async def test_enhance_transaction_with_tags_uses_moneywiz_tag_name_fields():
    """Transaction tags are resolved from MoneyWiz's tag relation table."""
    mock_db = AsyncMock()

    def mock_execute_query(query, params):
        if "FROM Z_36TAGS" in query:
            return [{"tag_id": 35}, {"tag_id": 36}]
        if "Z_ENT = 35" in query and params[0] == 35:
            return [{"ZNAME6": "Business"}]
        if "Z_ENT = 35" in query and params[0] == 36:
            return [{"ZNAME": "Tax"}]
        return []

    mock_db.execute_query.side_effect = mock_execute_query
    service = TransactionService(mock_db)
    transaction = TransactionModel.from_raw_data(
        {
            "Z_PK": 1,
            "Z_ENT": 47,
            "ZACCOUNT2": 123,
            "ZAMOUNT1": -50.0,
            "ZDATE1": 0,
            "ZDESC2": "Office supplies",
            "ZRECONCILED": 0,
        }
    )

    await service._enhance_transaction_with_tags(transaction)

    assert transaction.tags == ["Business", "Tax"]


@pytest.mark.asyncio
async def test_enhance_transaction_with_tags_defaults_to_empty_list_on_error():
    """Missing or changed tag tables should not fail transaction retrieval."""
    mock_db = AsyncMock()
    mock_db.execute_query.side_effect = RuntimeError("missing table")
    service = TransactionService(mock_db)
    transaction = TransactionModel.from_raw_data({"Z_PK": 1, "Z_ENT": 47})

    await service._enhance_transaction_with_tags(transaction)

    assert transaction.tags == []
