"""Tests for TrendService - TDD approach for Phase 3 features."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from moneywiz_mcp_server.models.transaction import TransactionModel, TransactionType
from moneywiz_mcp_server.services.trend_service import TrendService


class TestTrendService:
    """Test suite for TrendService following TDD principles."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        return AsyncMock()

    @pytest.fixture
    def trend_service(self, mock_db_manager):
        """Create TrendService instance with mocked dependencies."""
        return TrendService(mock_db_manager)

    @pytest.fixture
    def sample_transactions(self):
        """Create sample transaction data for testing."""
        base_date = datetime.now() - timedelta(days=90)
        transactions = []

        # Create transactions across 3 months
        for month in range(3):
            month_date = base_date + timedelta(days=month * 30)

            # Groceries - increasing trend
            for i in range(5):
                transaction = TransactionModel(
                    id=f"grocery_{month}_{i}",
                    entity_id=47,  # Withdraw
                    account_id="account_1",
                    amount=Decimal(f"-{100 + month * 10}"),  # Increasing: 100, 110, 120
                    date=month_date + timedelta(days=i * 2),
                    description=f"Grocery Store {i}",
                    transaction_type=TransactionType.WITHDRAW,
                    category="Groceries",
                    currency="USD",
                )
                transactions.append(transaction)

            # Entertainment - decreasing trend
            for i in range(3):
                transaction = TransactionModel(
                    id=f"entertainment_{month}_{i}",
                    entity_id=47,
                    account_id="account_1",
                    amount=Decimal(f"-{80 - month * 5}"),  # Decreasing: 80, 75, 70
                    date=month_date + timedelta(days=i * 3),
                    description=f"Entertainment {i}",
                    transaction_type=TransactionType.WITHDRAW,
                    category="Entertainment",
                    currency="USD",
                )
                transactions.append(transaction)

        return transactions

    @pytest.mark.asyncio
    async def test_analyze_spending_trends_basic(
        self, trend_service, sample_transactions
    ):
        """Test basic spending trend analysis."""
        # Arrange
        months = 3

        # Mock transaction service
        mock_transaction_service = AsyncMock()
        mock_transaction_service.get_transactions.return_value = sample_transactions

        with patch(
            "moneywiz_mcp_server.services.trend_service.TransactionService",
            return_value=mock_transaction_service,
        ):
            # Act
            result = await trend_service.analyze_spending_trends(months=months)

        # Assert
        assert "period" in result
        assert "monthly_data" in result
        assert "statistics" in result
        assert "insights" in result
        assert "projections" in result
        assert "visualizations" in result

        # Check period
        period = result["period"]
        assert period["months_analyzed"] == months
        assert "start_date" in period
        assert "end_date" in period

        # Check statistics
        stats = result["statistics"]
        assert "average_monthly" in stats
        assert "median_monthly" in stats
        assert "trend_direction" in stats
        assert "growth_rate" in stats

        # Verify transaction service was called
        mock_transaction_service.get_transactions.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_category_trends(self, trend_service):
        """Test category-specific trend analysis."""
        # Arrange
        months = 6
        top_n = 5

        # Mock expense summary data
        mock_expense_summary = {
            "category_breakdown": [
                type(
                    "CategoryExpense",
                    (),
                    {
                        "category_name": "Groceries",
                        "total_amount": Decimal("600.00"),
                        "percentage_of_total": 30.0,
                    },
                )(),
                type(
                    "CategoryExpense",
                    (),
                    {
                        "category_name": "Entertainment",
                        "total_amount": Decimal("400.00"),
                        "percentage_of_total": 20.0,
                    },
                )(),
            ]
        }

        mock_transaction_service = AsyncMock()
        mock_transaction_service.get_expense_summary.return_value = mock_expense_summary

        # Mock the individual trend analysis for each category
        trend_service.analyze_spending_trends = AsyncMock()
        trend_service.analyze_spending_trends.return_value = {
            "statistics": {
                "trend_direction": "increasing",
                "growth_rate": 5.0,
                "average_monthly": 200.0,
            },
            "insights": [
                {
                    "type": "info",
                    "title": "Test insight",
                    "description": "Test",
                    "priority": "low",
                }
            ],
        }

        with patch(
            "moneywiz_mcp_server.services.trend_service.TransactionService",
            return_value=mock_transaction_service,
        ):
            # Act
            result = await trend_service.analyze_category_trends(
                months=months, top_n=top_n
            )

        # Assert
        assert "period" in result
        assert "category_trends" in result
        assert "overall_insights" in result

        # Check category trends
        category_trends = result["category_trends"]
        assert len(category_trends) <= top_n

        for trend in category_trends:
            assert "category" in trend
            assert "total_spent" in trend
            assert "percentage_of_total" in trend
            assert "trend" in trend
            assert "growth_rate" in trend
            assert "insights" in trend

    @pytest.mark.asyncio
    async def test_analyze_income_vs_expense_trends(self, trend_service):
        """Test income vs expense trend analysis."""
        # Arrange
        months = 12

        # Mock income/expense data for each month
        mock_income_expense = type(
            "IncomeExpense",
            (),
            {
                "total_income": Decimal("5000.00"),
                "total_expenses": Decimal("4000.00"),
                "net_savings": Decimal("1000.00"),
                "savings_rate": Decimal("20.0"),
            },
        )()

        mock_transaction_service = AsyncMock()
        mock_transaction_service.get_income_vs_expense.return_value = (
            mock_income_expense
        )

        with patch(
            "moneywiz_mcp_server.services.trend_service.TransactionService",
            return_value=mock_transaction_service,
        ):
            # Act
            result = await trend_service.analyze_income_vs_expense_trends(months=months)

        # Assert
        assert "period" in result
        assert "monthly_data" in result
        assert "trends" in result
        assert "insights" in result

        # Check monthly data
        monthly_data = result["monthly_data"]
        assert len(monthly_data) == months

        for month_data in monthly_data:
            assert "month" in month_data
            assert "income" in month_data
            assert "expenses" in month_data
            assert "net_savings" in month_data
            assert "savings_rate" in month_data

        # Check trends
        trends = result["trends"]
        assert "income" in trends
        assert "expenses" in trends
        assert "savings_rate" in trends

        for trend_key, trend_data in trends.items():
            assert "direction" in trend_data
            if trend_key == "savings_rate":
                assert "improving" in trend_data

    def test_calculate_trend_metrics_increasing(self, trend_service):
        """Test trend calculation for increasing values."""
        # Arrange - steadily increasing values
        values = [100.0, 110.0, 120.0, 130.0, 140.0]

        # Act
        metrics = trend_service._calculate_trend_metrics(values)

        # Assert
        assert metrics["direction"] == "increasing"
        assert metrics["growth_rate"] > 0
        assert metrics["average"] == 120.0  # Mean of values
        assert metrics["strength"] in ["weak", "moderate", "strong"]

    def test_calculate_trend_metrics_decreasing(self, trend_service):
        """Test trend calculation for decreasing values."""
        # Arrange - steadily decreasing values
        values = [140.0, 130.0, 120.0, 110.0, 100.0]

        # Act
        metrics = trend_service._calculate_trend_metrics(values)

        # Assert
        assert metrics["direction"] == "decreasing"
        assert metrics["growth_rate"] < 0
        assert metrics["average"] == 120.0

    def test_calculate_trend_metrics_stable(self, trend_service):
        """Test trend calculation for stable values."""
        # Arrange - relatively stable values
        values = [100.0, 101.0, 99.0, 100.5, 99.5]

        # Act
        metrics = trend_service._calculate_trend_metrics(values)

        # Assert
        assert metrics["direction"] == "stable"
        assert abs(metrics["growth_rate"]) < 2  # Should be small

    def test_calculate_trend_metrics_empty(self, trend_service):
        """Test trend calculation with empty values."""
        # Arrange
        values = []

        # Act
        metrics = trend_service._calculate_trend_metrics(values)

        # Assert
        assert metrics["direction"] == "stable"
        assert metrics["growth_rate"] == 0
        assert metrics["average"] == 0

    def test_generate_trend_insights_increasing(self, trend_service):
        """Test insight generation for rapidly increasing expenses."""
        # Arrange - strong increasing trend
        trend_data = {
            "direction": "increasing",
            "strength": "strong",
            "growth_rate": 15.0,  # 15% monthly growth
            "std_dev": 50.0,
            "average": 500.0,
        }

        # Act
        insights = trend_service._generate_trend_insights(trend_data)

        # Assert
        assert len(insights) > 0

        # Should generate warning for rapid increase
        warning_insights = [i for i in insights if i["type"] == "warning"]
        assert len(warning_insights) > 0

        warning = warning_insights[0]
        assert "increasing" in warning["title"].lower()
        assert warning["priority"] == "high"

    def test_generate_trend_insights_decreasing(self, trend_service):
        """Test insight generation for decreasing expenses (positive)."""
        # Arrange - strong decreasing trend
        trend_data = {
            "direction": "decreasing",
            "strength": "strong",
            "growth_rate": -12.0,  # 12% monthly decrease
            "std_dev": 30.0,
            "average": 400.0,
        }

        # Act
        insights = trend_service._generate_trend_insights(trend_data)

        # Assert
        positive_insights = [i for i in insights if i["type"] == "positive"]
        assert len(positive_insights) > 0

        positive = positive_insights[0]
        assert (
            "progress" in positive["title"].lower()
            or "decreasing" in positive["description"].lower()
        )

    def test_calculate_projections(self, trend_service):
        """Test future spending projections."""
        # Arrange
        trend_data = {
            "direction": "increasing",
            "average": 1000.0,
            "growth_rate": 5.0,  # 5% monthly growth
            "strength": "moderate",
        }

        # Act
        projections = trend_service._calculate_projections(trend_data, months_ahead=3)

        # Assert
        assert len(projections) == 3

        for i, projection in enumerate(projections):
            assert "month" in projection
            assert "projected_amount" in projection
            assert "confidence" in projection

            # Amount should increase each month
            expected_amount = 1000.0 * (1.05 ** (i + 1))
            assert abs(projection["projected_amount"] - expected_amount) < 1.0

    def test_group_transactions_by_month(self, trend_service, sample_transactions):
        """Test transaction grouping by month."""
        # Act
        grouped = trend_service._group_transactions_by_month(sample_transactions)

        # Assert
        assert len(grouped) <= 3  # Should have up to 3 months

        for month_key, transactions in grouped.items():
            # Check month key format
            assert len(month_key) == 7  # YYYY-MM format
            assert "-" in month_key

            # All transactions in group should be expenses
            for transaction in transactions:
                assert transaction.is_expense()


if __name__ == "__main__":
    pytest.main([__file__])
