"""Integration tests for budget functionality."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from moneywiz_mcp_server.config import Config
from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.main import (
    analyze_budget_performance,
    get_budget_vs_actual,
    get_budgets,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock(spec=Config)
    config.database_path = "/mock/path/to/database.sqlite"
    config.read_only = True
    return config


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager with realistic data."""
    db_manager = MagicMock(spec=DatabaseManager)
    db_manager.initialize = AsyncMock()
    db_manager.close = AsyncMock()
    db_manager.execute_query = AsyncMock()
    return db_manager


@pytest.fixture
def sample_budget_records():
    """Sample database records for budgets (Entity 18)."""
    return [
        {
            "Z_PK": 1919,
            "Z_ENT": 18,
            "ZOPENINGBALANCE1": 500.00,  # Groceries budget
            "ZDURATION": 1,
            "ZDURATIONUNITS": 8,  # Monthly
            "ZISREPEATABLE": 1,
            "ZOBJECTCREATIONDATE": 739910709.269467,
            "ZBALANCE": 0.0,
        },
        {
            "Z_PK": 2117,
            "Z_ENT": 18,
            "ZOPENINGBALANCE1": 200.00,  # Entertainment budget
            "ZDURATION": 1,
            "ZDURATIONUNITS": 8,  # Monthly
            "ZISREPEATABLE": 1,
            "ZOBJECTCREATIONDATE": 739910709.42324,
            "ZBALANCE": 0.0,
        },
        {
            "Z_PK": 5012,
            "Z_ENT": 18,
            "ZOPENINGBALANCE1": 1000.00,  # Transportation budget
            "ZDURATION": 1,
            "ZDURATIONUNITS": 8,  # Monthly
            "ZISREPEATABLE": 1,
            "ZOBJECTCREATIONDATE": 739910711.406963,
            "ZBALANCE": 0.0,
        },
    ]


class TestGetBudgetsIntegration:
    """Integration tests for get_budgets tool."""

    @pytest.mark.asyncio
    async def test_get_budgets_returns_list(
        self, mock_db_manager, mock_config, sample_budget_records
    ):
        """Test that get_budgets returns a list of budgets."""
        # Setup mock responses
        mock_db_manager.execute_query.side_effect = [
            sample_budget_records,  # Budget query
            [{"category_name": "Groceries"}],  # Category for budget 1
            [],  # Linked accounts for budget 1
            [{"spent": 350.0, "count": 15}],  # Spent for budget 1
            [],  # ZPASTPERIODSBUDGET spent
            [{"category_name": "Entertainment"}],  # Category for budget 2
            [],  # Linked accounts for budget 2
            [{"spent": 180.0, "count": 8}],  # Spent for budget 2
            [],  # ZPASTPERIODSBUDGET spent
            [{"category_name": "Transportation"}],  # Category for budget 3
            [],  # Linked accounts for budget 3
            [{"spent": 500.0, "count": 20}],  # Spent for budget 3
            [],  # ZPASTPERIODSBUDGET spent
        ]

        with (
            patch(
                "moneywiz_mcp_server.main.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("moneywiz_mcp_server.main._config", mock_config),
        ):
            result = await get_budgets()

        assert result.total_count == 3
        assert len(result.budgets) == 3

    @pytest.mark.asyncio
    async def test_get_budgets_empty_database(self, mock_db_manager, mock_config):
        """Test get_budgets with no budgets in database."""
        mock_db_manager.execute_query.return_value = []

        with (
            patch(
                "moneywiz_mcp_server.main.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("moneywiz_mcp_server.main._config", mock_config),
        ):
            result = await get_budgets()

        assert result.total_count == 0
        assert len(result.budgets) == 0


class TestAnalyzeBudgetPerformanceIntegration:
    """Integration tests for analyze_budget_performance tool."""

    @pytest.mark.asyncio
    async def test_analyze_returns_analysis(
        self, mock_db_manager, mock_config, sample_budget_records
    ):
        """Test that analyze_budget_performance returns analysis data."""
        mock_db_manager.execute_query.side_effect = [
            sample_budget_records,  # Budget query
            [{"category_name": "Groceries"}],
            [],
            [{"spent": 350.0, "count": 15}],
            [],
            [{"category_name": "Entertainment"}],
            [],
            [{"spent": 180.0, "count": 8}],
            [],
            [{"category_name": "Transportation"}],
            [],
            [{"spent": 500.0, "count": 20}],
            [],
        ]

        with (
            patch(
                "moneywiz_mcp_server.main.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("moneywiz_mcp_server.main._config", mock_config),
        ):
            result = await analyze_budget_performance()

        assert result.analysis_period == "current_month"
        assert result.budgets_on_track >= 0
        assert result.overall_status in [
            "on_track",
            "at_risk",
            "over_budget",
            "no_data",
        ]

    @pytest.mark.asyncio
    async def test_analyze_empty_database(self, mock_db_manager, mock_config):
        """Test analysis with no budgets."""
        mock_db_manager.execute_query.return_value = []

        with (
            patch(
                "moneywiz_mcp_server.main.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("moneywiz_mcp_server.main._config", mock_config),
        ):
            result = await analyze_budget_performance()

        assert result.overall_status == "no_data"


class TestBudgetVsActualIntegration:
    """Integration tests for get_budget_vs_actual tool."""

    @pytest.mark.asyncio
    async def test_budget_vs_actual_returns_comparison(
        self, mock_db_manager, mock_config, sample_budget_records
    ):
        """Test that get_budget_vs_actual returns comparison data."""
        mock_db_manager.execute_query.side_effect = [
            sample_budget_records,
            [{"category_name": "Groceries"}],
            [],
            [{"spent": 350.0, "count": 15}],
            [],
            [{"category_name": "Entertainment"}],
            [],
            [{"spent": 250.0, "count": 8}],  # Over budget
            [],
            [{"category_name": "Transportation"}],
            [],
            [{"spent": 500.0, "count": 20}],
            [],
        ]

        with (
            patch(
                "moneywiz_mcp_server.main.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("moneywiz_mcp_server.main._config", mock_config),
        ):
            result = await get_budget_vs_actual()

        assert result.period == "current_month"
        assert len(result.items) == 3

    @pytest.mark.asyncio
    async def test_budget_vs_actual_with_category_filter(
        self, mock_db_manager, mock_config
    ):
        """Test budget vs actual with category filter."""
        mock_db_manager.execute_query.side_effect = [
            [
                {
                    "Z_PK": 1919,
                    "Z_ENT": 18,
                    "ZOPENINGBALANCE1": 500.00,
                    "ZDURATION": 1,
                    "ZDURATIONUNITS": 8,
                    "ZISREPEATABLE": 1,
                    "ZOBJECTCREATIONDATE": 739910709.269467,
                    "ZBALANCE": 0.0,
                }
            ],
            [{"category_name": "Food"}],
            [],
            [{"spent": 350.0, "count": 15}],
            [],
        ]

        with (
            patch(
                "moneywiz_mcp_server.main.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("moneywiz_mcp_server.main._config", mock_config),
        ):
            result = await get_budget_vs_actual(category="Food")

        assert result.period == "current_month"
        # The filter is applied at the service level
        assert len(result.items) == 1


class TestBudgetToolErrors:
    """Test error handling in budget tools."""

    @pytest.mark.asyncio
    async def test_get_budgets_database_error(self, mock_db_manager, mock_config):
        """Test error handling when database query fails."""
        mock_db_manager.execute_query.side_effect = Exception("Database error")

        with (
            patch(
                "moneywiz_mcp_server.main.get_db_manager",
                return_value=mock_db_manager,
            ),
            patch("moneywiz_mcp_server.main._config", mock_config),
            pytest.raises(RuntimeError) as exc_info,
        ):
            await get_budgets()

        assert "Failed to get budgets" in str(exc_info.value)
