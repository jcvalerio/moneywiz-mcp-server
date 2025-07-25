"""Test data-driven category classification functionality."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from moneywiz_mcp_server.services.category_classification_service import (
    CategoryClassificationService,
    CategoryType,
)


class TestDataDrivenCategoryClassification:
    """Test suite for data-driven category classification."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        db_manager = AsyncMock()
        return db_manager

    @pytest.fixture
    def classification_service(self, mock_db_manager):
        """Create a category classification service with mocked database."""
        return CategoryClassificationService(mock_db_manager)

    @pytest.mark.asyncio
    async def test_learned_patterns_classification_income(
        self, classification_service, mock_db_manager
    ):
        """Test classification using learned patterns for income category."""
        # Mock the transaction pattern analysis to return income-like data
        mock_db_manager.execute_query.return_value = [
            {
                "category_id": 123,
                "transaction_count": 10,
                "positive_amount_ratio": 0.95,  # 95% positive amounts = income
                "avg_amount": 2500.0,
                "first_transaction": 12345.0,
                "last_transaction": 67890.0,
            }
        ]

        # Force refresh patterns
        await classification_service._analyze_user_transaction_patterns()

        # Test classification
        result = await classification_service._classify_from_learned_patterns(123)
        assert result == CategoryType.INCOME

    @pytest.mark.asyncio
    async def test_learned_patterns_classification_expense(
        self, classification_service, mock_db_manager
    ):
        """Test classification using learned patterns for expense category."""
        # Mock the transaction pattern analysis to return expense-like data
        mock_db_manager.execute_query.return_value = [
            {
                "category_id": 456,
                "transaction_count": 15,
                "positive_amount_ratio": 0.1,  # 10% positive amounts = expense
                "avg_amount": 150.0,
                "first_transaction": 12345.0,
                "last_transaction": 67890.0,
            }
        ]

        # Force refresh patterns
        await classification_service._analyze_user_transaction_patterns()

        # Test classification
        result = await classification_service._classify_from_learned_patterns(456)
        assert result == CategoryType.EXPENSE

    @pytest.mark.asyncio
    async def test_transaction_type_classification_deposit_income(
        self, classification_service, mock_db_manager
    ):
        """Test transaction type-based classification for deposit (income)."""
        # Mock transaction type analysis for DEPOSIT (ENT 37) with positive amounts
        mock_db_manager.execute_query.return_value = [
            {
                "entity_type": 37,  # DEPOSIT
                "usage_count": 5,
                "positive_ratio": 0.9,  # 90% positive = likely income
            }
        ]

        result = await classification_service._classify_from_transaction_types(789)
        assert result == CategoryType.INCOME

    @pytest.mark.asyncio
    async def test_transaction_type_classification_withdraw_expense(
        self, classification_service, mock_db_manager
    ):
        """Test transaction type-based classification for withdraw (expense)."""
        # Mock transaction type analysis for WITHDRAW (ENT 47) with negative amounts
        mock_db_manager.execute_query.return_value = [
            {
                "entity_type": 47,  # WITHDRAW
                "usage_count": 8,
                "positive_ratio": 0.1,  # 10% positive = likely expense
            }
        ]

        result = await classification_service._classify_from_transaction_types(987)
        assert result == CategoryType.EXPENSE

    @pytest.mark.asyncio
    async def test_transaction_type_classification_transfer(
        self, classification_service, mock_db_manager
    ):
        """Test transaction type-based classification for transfers."""
        # Mock transaction type analysis for TRANSFER (ENT 45)
        mock_db_manager.execute_query.return_value = [
            {
                "entity_type": 45,  # TRANSFER_IN
                "usage_count": 3,
                "positive_ratio": 0.5,
            }
        ]

        result = await classification_service._classify_from_transaction_types(654)
        assert result == CategoryType.TRANSFER

    @pytest.mark.asyncio
    async def test_fallback_logic_with_transaction_history(
        self, classification_service, mock_db_manager
    ):
        """Test fallback logic when category has transaction history."""
        # Mock transaction count query to show category has transactions
        mock_db_manager.execute_query.return_value = [{"count": 5}]

        result = await classification_service._classify_with_fallback_logic(
            321, ["Test Category"]
        )
        assert result == CategoryType.EXPENSE  # Default to expense when uncertain

    @pytest.mark.asyncio
    async def test_fallback_logic_no_transaction_history(
        self, classification_service, mock_db_manager
    ):
        """Test fallback logic when category has no transaction history."""
        # Mock transaction count query to show no transactions
        mock_db_manager.execute_query.return_value = [{"count": 0}]

        result = await classification_service._classify_with_fallback_logic(
            432, ["Test Category"]
        )
        assert result == CategoryType.UNKNOWN  # Conservative when no data

    @pytest.mark.asyncio
    async def test_adaptive_classification_pipeline(
        self, classification_service, mock_db_manager
    ):
        """Test the complete adaptive classification pipeline."""
        # Set up mock for learned patterns (high confidence income)
        classification_service._category_patterns_cache = {
            555: {
                "transaction_count": 12,
                "positive_amount_ratio": 0.9,
                "confidence_score": 0.85,
                "avg_amount": 3000.0,
                "first_transaction": 12345.0,
                "last_transaction": 67890.0,
            }
        }
        classification_service._patterns_last_updated = datetime.now()

        # Mock hierarchy for the category
        hierarchy = ["Other Income", "Freelance"]

        result = await classification_service._classify_category_adaptive(
            555, hierarchy
        )
        assert result == CategoryType.INCOME

    @pytest.mark.asyncio
    async def test_learned_patterns_stats(
        self, classification_service, mock_db_manager
    ):
        """Test learned patterns statistics generation."""
        # Set up mock patterns cache
        classification_service._category_patterns_cache = {
            100: {  # High confidence income
                "transaction_count": 10,
                "positive_amount_ratio": 0.9,
                "confidence_score": 0.9,
                "avg_amount": 2500.0,
                "first_transaction": 12345.0,
                "last_transaction": 67890.0,
            },
            200: {  # High confidence expense
                "transaction_count": 15,
                "positive_amount_ratio": 0.1,
                "confidence_score": 0.85,
                "avg_amount": 150.0,
                "first_transaction": 12345.0,
                "last_transaction": 67890.0,
            },
            300: {  # Mixed usage
                "transaction_count": 8,
                "positive_amount_ratio": 0.5,
                "confidence_score": 0.8,
                "avg_amount": 500.0,
                "first_transaction": 12345.0,
                "last_transaction": 67890.0,
            },
            400: {  # Low confidence
                "transaction_count": 3,
                "positive_amount_ratio": 0.8,
                "confidence_score": 0.3,
                "avg_amount": 100.0,
                "first_transaction": 12345.0,
                "last_transaction": 67890.0,
            },
        }
        classification_service._patterns_last_updated = datetime.now()

        stats = await classification_service.get_learned_patterns_stats()

        assert stats["total_learned_categories"] == 4
        assert stats["categories_by_type"]["high_confidence_income"] == 1
        assert stats["categories_by_type"]["high_confidence_expense"] == 1
        assert stats["categories_by_type"]["mixed_usage"] == 1
        assert stats["categories_by_type"]["low_confidence"] == 1
        assert (
            abs(stats["avg_confidence_score"] - 0.7125) < 0.001
        )  # (0.9 + 0.85 + 0.8 + 0.3) / 4

    @pytest.mark.asyncio
    async def test_cache_refresh_logic(self, classification_service, mock_db_manager):
        """Test that cache refresh logic works correctly."""
        # Set patterns to be stale (older than 24 hours)
        classification_service._patterns_last_updated = datetime.now() - timedelta(
            hours=25
        )

        # Mock the analysis query
        mock_db_manager.execute_query.return_value = [
            {
                "category_id": 100,
                "transaction_count": 5,
                "positive_amount_ratio": 0.8,
                "avg_amount": 100.0,
                "first_transaction": 12345.0,
                "last_transaction": 67890.0,
            }
        ]

        # This should trigger a refresh
        await classification_service._refresh_learned_patterns_if_needed()

        # Verify the patterns were refreshed
        assert classification_service._patterns_last_updated is not None
        assert len(classification_service._category_patterns_cache) == 1
        assert 100 in classification_service._category_patterns_cache

    def test_clear_cache_includes_new_caches(self, classification_service):
        """Test that clear_cache clears all caches including learned patterns."""
        # Set up some cached data
        classification_service._category_type_cache[123] = CategoryType.INCOME
        classification_service._category_patterns_cache[456] = {"test": "data"}
        classification_service._patterns_last_updated = datetime.now()

        # Clear cache
        classification_service.clear_cache()

        # Verify all caches are cleared
        assert len(classification_service._category_type_cache) == 0
        assert len(classification_service._category_patterns_cache) == 0
        assert classification_service._patterns_last_updated is None
