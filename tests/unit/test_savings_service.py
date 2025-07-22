"""Tests for SavingsService - TDD approach for Phase 3 features."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from moneywiz_mcp_server.models.analytics_result import (
    CategoryExpense,
    IncomeExpenseAnalysis,
)
from moneywiz_mcp_server.models.transaction import DateRange
from moneywiz_mcp_server.services.savings_service import SavingsService


class TestSavingsService:
    """Test suite for SavingsService following TDD principles."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        mock_db = AsyncMock()
        return mock_db

    @pytest.fixture
    def savings_service(self, mock_db_manager):
        """Create SavingsService instance with mocked dependencies."""
        return SavingsService(mock_db_manager)

    @pytest.fixture
    def sample_income_expense_data(self):
        """Sample income vs expense data for testing."""
        from datetime import datetime

        return IncomeExpenseAnalysis(
            total_income=Decimal("5000.00"),
            total_expenses=Decimal("4000.00"),
            net_savings=Decimal("1000.00"),
            savings_rate=20.0,  # float not Decimal
            income_breakdown=[],
            expense_breakdown=[],
            analysis_period=DateRange(
                start_date=datetime(2024, 1, 1), end_date=datetime(2024, 3, 31)
            ),
            currency="USD",
            monthly_averages={},
        )

    @pytest.fixture
    def sample_category_expenses(self):
        """Sample category expense data for testing."""
        return [
            CategoryExpense(
                category_name="Groceries",
                category_id=1,
                total_amount=Decimal("800.00"),
                transaction_count=20,
                average_amount=Decimal("40.00"),
                percentage_of_total=20.0,
            ),
            CategoryExpense(
                category_name="Entertainment",
                category_id=2,
                total_amount=Decimal("600.00"),
                transaction_count=15,
                average_amount=Decimal("40.00"),
                percentage_of_total=15.0,
            ),
            CategoryExpense(
                category_name="Dining Out",
                category_id=3,
                total_amount=Decimal("400.00"),
                transaction_count=10,
                average_amount=Decimal("40.00"),
                percentage_of_total=10.0,
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_savings_recommendations_basic(
        self, savings_service, sample_income_expense_data, sample_category_expenses
    ):
        """Test basic savings recommendations generation."""
        # Arrange
        start_date = datetime.now() - timedelta(days=90)
        end_date = datetime.now()
        target_rate = 25.0

        # Mock transaction service calls
        savings_service.db_manager = AsyncMock()

        # Create mock transaction service
        mock_transaction_service = AsyncMock()
        mock_transaction_service.get_income_vs_expense.return_value = (
            sample_income_expense_data
        )
        mock_transaction_service.get_expense_summary.return_value = {
            "category_breakdown": sample_category_expenses
        }

        # Patch the import to return our mock
        with patch(
            "moneywiz_mcp_server.services.transaction_service.TransactionService",
            return_value=mock_transaction_service,
        ):
            # Act
            result = await savings_service.get_savings_recommendations(
                start_date=start_date,
                end_date=end_date,
                target_savings_rate=target_rate,
            )

        # Assert
        assert "current_state" in result
        assert "target_state" in result
        assert "recommendations" in result
        assert "insights" in result

        # Check current state
        current_state = result["current_state"]
        assert current_state["savings_rate"] == 20.0
        assert current_state["total_income"] == 5000.0
        assert current_state["total_expenses"] == 4000.0

        # Check target state
        target_state = result["target_state"]
        assert target_state["target_savings_rate"] == 25.0

        # Check recommendations exist
        assert len(result["recommendations"]) > 0

        # Verify transaction service was called
        mock_transaction_service.get_income_vs_expense.assert_called_once()
        # get_expense_summary is called multiple times in the savings service
        assert mock_transaction_service.get_expense_summary.call_count >= 1

    @pytest.mark.asyncio
    async def test_category_recommendations_high_spending(
        self, savings_service, sample_category_expenses
    ):
        """Test that high spending categories generate recommendations."""
        # Arrange - Create a category with >20% spending
        high_spending_category = CategoryExpense(
            category_name="High Spending Category",
            category_id=4,
            total_amount=Decimal("1200.00"),
            transaction_count=30,
            average_amount=Decimal("40.00"),
            percentage_of_total=30.0,  # >20% triggers recommendation
        )

        categories = [high_spending_category, *sample_category_expenses]
        total_expenses = 4000.0

        # Act
        result = await savings_service._get_category_recommendations(
            categories, total_expenses
        )

        # Assert
        recommendations = result["recommendations"]
        assert len(recommendations) > 0

        # Check for high spending category recommendation
        high_spending_recs = [
            r for r in recommendations if r["category"] == "High Spending Category"
        ]
        assert len(high_spending_recs) > 0

        # Verify recommendation details
        rec = high_spending_recs[0]
        assert rec["type"] == "category_reduction"
        assert rec["priority"] == "high"
        assert "reducing by 15%" in rec["description"].lower()

    @pytest.mark.asyncio
    async def test_discretionary_spending_recommendations(
        self, savings_service, sample_category_expenses
    ):
        """Test that discretionary categories generate specific recommendations."""
        # Arrange - Add discretionary categories
        discretionary_category = CategoryExpense(
            category_name="Entertainment",
            category_id=5,
            total_amount=Decimal("600.00"),
            transaction_count=15,
            average_amount=Decimal("40.00"),
            percentage_of_total=15.0,
        )

        categories = [discretionary_category]
        total_expenses = 4000.0

        # Act
        result = await savings_service._get_category_recommendations(
            categories, total_expenses
        )

        # Assert
        recommendations = result["recommendations"]
        entertainment_recs = [
            r for r in recommendations if r["category"] == "Entertainment"
        ]

        if entertainment_recs:  # Entertainment is in discretionary list
            rec = entertainment_recs[0]
            assert rec["type"] == "discretionary_reduction"
            assert rec["priority"] == "medium"
            assert rec["difficulty"] == "easy"
            assert "tips" in rec

    @pytest.mark.asyncio
    async def test_target_savings_calculation(self, savings_service):
        """Test calculation of needed expense reduction for target savings rate."""
        # Arrange
        income = 5000.0
        expenses = 4000.0
        target_rate = 25.0  # Want 25% savings rate

        # Act
        needed_reduction = savings_service._calculate_needed_expense_reduction(
            income, expenses, target_rate
        )

        # Assert
        # Target expenses should be 5000 * (1 - 0.25) = 3750
        # Current expenses are 4000
        # So need to reduce by 4000 - 3750 = 250
        assert needed_reduction == 250.0

    @pytest.mark.asyncio
    async def test_category_saving_tips(self, savings_service):
        """Test that category-specific saving tips are provided."""
        # Test various categories
        dining_tips = savings_service._get_category_saving_tips("dining out")
        assert "cook more meals" in dining_tips[0].lower()

        entertainment_tips = savings_service._get_category_saving_tips("entertainment")
        assert "free local events" in entertainment_tips[0].lower()

        groceries_tips = savings_service._get_category_saving_tips("groceries")
        assert "meal plan" in groceries_tips[0].lower()

        # Test unknown category
        unknown_tips = savings_service._get_category_saving_tips("unknown category")
        assert "review spending" in unknown_tips[0].lower()

    @pytest.mark.asyncio
    async def test_fixed_vs_variable_analysis(
        self, savings_service, sample_category_expenses
    ):
        """Test fixed vs variable expense analysis."""
        # Arrange
        start_date = datetime.now() - timedelta(days=90)
        end_date = datetime.now()

        # Mock transaction service
        mock_transaction_service = AsyncMock()
        mock_transaction_service.get_expense_summary.return_value = {
            "category_breakdown": sample_category_expenses
        }

        with patch(
            "moneywiz_mcp_server.services.transaction_service.TransactionService",
            return_value=mock_transaction_service,
        ):
            # Act
            result = await savings_service._analyze_fixed_vs_variable_expenses(
                start_date, end_date
            )

        # Assert
        assert "recommendations" in result
        assert "insights" in result

        insights = result["insights"]
        assert "fixed_percentage" in insights
        assert "variable_percentage" in insights
        assert insights["fixed_percentage"] + insights["variable_percentage"] == 100.0


if __name__ == "__main__":
    pytest.main([__file__])
