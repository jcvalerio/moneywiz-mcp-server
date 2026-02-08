"""Unit tests for BudgetService."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.budget import (
    BudgetModel,
    BudgetPeriod,
    BudgetStatus,
)
from moneywiz_mcp_server.services.budget_service import BudgetService


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    db_manager = MagicMock(spec=DatabaseManager)
    db_manager.execute_query = AsyncMock()
    return db_manager


@pytest.fixture
def budget_service(mock_db_manager):
    """Create a BudgetService with mock database."""
    return BudgetService(mock_db_manager)


@pytest.fixture
def sample_budget_record():
    """Sample database record for budget (Entity 18)."""
    return {
        "Z_PK": 1919,
        "Z_ENT": 18,
        "ZOPENINGBALANCE1": 20000.0,
        "ZDURATION": 1,
        "ZDURATIONUNITS": 8,  # Monthly
        "ZISREPEATABLE": 1,
        "ZOBJECTCREATIONDATE": 739910709.269467,  # Core Data timestamp
        "ZBALANCE": 0.0,
        "ZCARRIEDBALANCE": 0.0,
    }


class TestBudgetService:
    """Test cases for BudgetService."""

    @pytest.mark.asyncio
    async def test_get_budgets_empty_result(self, budget_service, mock_db_manager):
        """Test getting budgets when none exist."""
        mock_db_manager.execute_query.return_value = []

        result = await budget_service.get_budgets()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_budgets_with_data(
        self, budget_service, mock_db_manager, sample_budget_record
    ):
        """Test getting budgets with sample data."""
        # Mock budget records
        mock_db_manager.execute_query.side_effect = [
            [sample_budget_record],  # Budget query
            [{"category_name": "Groceries"}],  # Category query
            [],  # Linked accounts query
            [{"spent": 5000.0, "count": 10}],  # Spent amount query
        ]

        result = await budget_service.get_budgets(limit=5)

        assert len(result) == 1
        assert result[0].budget_amount == Decimal("20000.0")
        assert result[0].period == BudgetPeriod.MONTHLY

    @pytest.mark.asyncio
    async def test_get_budgets_with_filter(
        self, budget_service, mock_db_manager, sample_budget_record
    ):
        """Test filtering budgets by category."""
        mock_db_manager.execute_query.side_effect = [
            [sample_budget_record],
            [{"category_name": "Food"}],
            [],
            [{"spent": None, "count": 0}],
        ]

        result = await budget_service.get_budgets(categories=["Food"])

        assert len(result) == 1
        assert "Food" in result[0].categories

    @pytest.mark.asyncio
    async def test_get_budgets_filter_no_match(
        self, budget_service, mock_db_manager, sample_budget_record
    ):
        """Test filtering budgets with no matching category."""
        mock_db_manager.execute_query.side_effect = [
            [sample_budget_record],
            [{"category_name": "Food"}],
            [],
            [{"spent": None, "count": 0}],
        ]

        result = await budget_service.get_budgets(categories=["Entertainment"])

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_budgets_period_filter(
        self, budget_service, mock_db_manager, sample_budget_record
    ):
        """Test filtering budgets by period."""
        mock_db_manager.execute_query.side_effect = [
            [sample_budget_record],
            [{"category_name": "Food"}],
            [],
            [{"spent": None, "count": 0}],
        ]

        result = await budget_service.get_budgets(period="monthly")

        assert len(result) == 1
        assert result[0].period == BudgetPeriod.MONTHLY

    @pytest.mark.asyncio
    async def test_get_budget_analysis_empty(self, budget_service, mock_db_manager):
        """Test budget analysis with no budgets."""
        mock_db_manager.execute_query.return_value = []

        result = await budget_service.get_budget_analysis()

        assert result["overall_status"] == "no_data"
        assert result["budgets_on_track"] == 0

    @pytest.mark.asyncio
    async def test_get_budget_vs_actual_empty(self, budget_service, mock_db_manager):
        """Test budget vs actual with no budgets."""
        mock_db_manager.execute_query.return_value = []

        result = await budget_service.get_budget_vs_actual()

        assert result["period"] == "current_month"
        assert len(result["items"]) == 0


class TestBudgetServiceHelpers:
    """Test cases for BudgetService helper methods."""

    def test_duration_units_mapping(self, budget_service):
        """Test that duration units are mapped correctly."""
        assert budget_service.DURATION_UNITS[1] == BudgetPeriod.DAILY
        assert budget_service.DURATION_UNITS[2] == BudgetPeriod.WEEKLY
        assert budget_service.DURATION_UNITS[4] == BudgetPeriod.YEARLY
        assert budget_service.DURATION_UNITS[8] == BudgetPeriod.MONTHLY

    def test_core_data_timestamp_conversion(self, budget_service):
        """Test Core Data timestamp conversion."""
        # Core Data epoch is Jan 1, 2001
        timestamp = 0.0
        result = budget_service._core_data_timestamp_to_datetime(timestamp)
        assert result == datetime(2001, 1, 1)

    def test_datetime_to_core_data_timestamp(self, budget_service):
        """Test datetime to Core Data timestamp conversion."""
        dt = datetime(2001, 1, 1)
        result = budget_service._datetime_to_core_data_timestamp(dt)
        assert result == 0.0

    def test_generate_recommendations_over_budget(self, budget_service):
        """Test recommendations for over budget scenarios."""
        budgets = [
            BudgetModel(
                id="1",
                budget_amount=Decimal("100"),
                currency="USD",
                period=BudgetPeriod.MONTHLY,
                status=BudgetStatus.OVER_BUDGET,
                categories=["Food"],
            )
        ]
        recommendations = budget_service._generate_recommendations(budgets, 110.0, 1)
        assert any("over limit" in r for r in recommendations)

    def test_generate_recommendations_on_track(self, budget_service):
        """Test recommendations for on track scenarios."""
        budgets = [
            BudgetModel(
                id="1",
                budget_amount=Decimal("100"),
                currency="USD",
                period=BudgetPeriod.MONTHLY,
                status=BudgetStatus.ON_TRACK,
            )
        ]
        recommendations = budget_service._generate_recommendations(budgets, 40.0, 0)
        assert any("Good job" in r or "on track" in r for r in recommendations)


class TestBudgetServiceFilters:
    """Test cases for budget filtering logic."""

    @pytest.mark.asyncio
    async def test_matches_filters_no_filters(self, budget_service):
        """Test that budget matches when no filters applied."""
        budget = BudgetModel(
            id="1",
            budget_amount=Decimal("100"),
            currency="USD",
            period=BudgetPeriod.MONTHLY,
            categories=["Food"],
        )
        result = await budget_service._matches_filters(budget, None, None)
        assert result is True

    @pytest.mark.asyncio
    async def test_matches_filters_category_match(self, budget_service):
        """Test category filter matching."""
        budget = BudgetModel(
            id="1",
            budget_amount=Decimal("100"),
            currency="USD",
            period=BudgetPeriod.MONTHLY,
            categories=["Food", "Groceries"],
        )
        result = await budget_service._matches_filters(budget, ["food"], None)
        assert result is True

    @pytest.mark.asyncio
    async def test_matches_filters_category_no_match(self, budget_service):
        """Test category filter not matching."""
        budget = BudgetModel(
            id="1",
            budget_amount=Decimal("100"),
            currency="USD",
            period=BudgetPeriod.MONTHLY,
            categories=["Food"],
        )
        result = await budget_service._matches_filters(budget, ["Entertainment"], None)
        assert result is False

    @pytest.mark.asyncio
    async def test_matches_filters_period_match(self, budget_service):
        """Test period filter matching."""
        budget = BudgetModel(
            id="1",
            budget_amount=Decimal("100"),
            currency="USD",
            period=BudgetPeriod.MONTHLY,
        )
        result = await budget_service._matches_filters(budget, None, "monthly")
        assert result is True

    @pytest.mark.asyncio
    async def test_matches_filters_period_no_match(self, budget_service):
        """Test period filter not matching."""
        budget = BudgetModel(
            id="1",
            budget_amount=Decimal("100"),
            currency="USD",
            period=BudgetPeriod.MONTHLY,
        )
        result = await budget_service._matches_filters(budget, None, "weekly")
        assert result is False
