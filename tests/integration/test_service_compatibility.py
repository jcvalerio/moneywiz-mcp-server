"""Integration tests for service compatibility and data structure consistency.

This test suite ensures that changes to one service don't break other dependent services.
It focuses on testing the data contracts between services to catch regressions like the
CategoryExpense object structure issue.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from moneywiz_mcp_server.models.analytics_result import CategoryExpense
from moneywiz_mcp_server.models.savings_responses import (
    CategoryTrendsResponse,
    IncomeVsExpenseTrendsResponse,
    SavingsOptimizationResponse,
    SpendingTrendResponse,
)
from moneywiz_mcp_server.services.savings_service import SavingsService
from moneywiz_mcp_server.services.transaction_service import TransactionService
from moneywiz_mcp_server.services.trend_service import TrendService
from moneywiz_mcp_server.utils.date_utils import parse_natural_language_date


class TestServiceCompatibility:
    """Test compatibility between services to prevent data structure regressions."""

    @pytest.fixture
    async def services(self, mock_database_manager):
        """Create service instances for testing."""
        transaction_service = TransactionService(mock_database_manager)
        savings_service = SavingsService(mock_database_manager)
        trend_service = TrendService(mock_database_manager)

        return {
            "transaction": transaction_service,
            "savings": savings_service,
            "trend": trend_service,
        }

    @pytest.fixture
    def date_range(self):
        """Create a standard date range for testing."""
        return parse_natural_language_date("last 3 months")

    async def test_get_expense_summary_returns_category_expense_objects(
        self, services, date_range
    ):
        """Test that get_expense_summary returns proper CategoryExpense objects."""
        transaction_service = services["transaction"]

        # Get expense summary
        expense_summary = await transaction_service.get_expense_summary(
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            group_by="category",
        )

        # Verify structure
        assert "category_breakdown" in expense_summary
        assert "total_expenses_by_currency" in expense_summary

        # Verify CategoryExpense objects
        categories = expense_summary["category_breakdown"]
        assert isinstance(categories, list)

        if categories:  # Only test if we have data
            category = categories[0]
            assert isinstance(category, CategoryExpense)

            # Verify required attributes exist
            assert hasattr(category, "category_name")
            assert hasattr(category, "total_amount")
            assert hasattr(category, "transaction_count")
            assert hasattr(category, "average_amount")
            assert hasattr(category, "percentage_of_total")

            # Verify types
            assert isinstance(category.category_name, str)
            assert isinstance(category.total_amount, Decimal)
            assert isinstance(category.transaction_count, int)
            assert isinstance(category.average_amount, Decimal)
            assert isinstance(category.percentage_of_total, float)

            # Verify multi-currency attributes for API compatibility
            assert hasattr(category, "amounts_by_currency")
            assert hasattr(category, "transaction_counts_by_currency")
            assert isinstance(category.amounts_by_currency, dict)
            assert isinstance(category.transaction_counts_by_currency, dict)

    async def test_income_vs_expense_analysis_compatibility(self, services, date_range):
        """Test that income vs expense analysis works with CategoryExpense objects."""
        transaction_service = services["transaction"]

        # This should not raise any AttributeError
        income_expense_analysis = await transaction_service.get_income_vs_expense(
            start_date=date_range.start_date, end_date=date_range.end_date
        )

        # Verify structure
        assert hasattr(income_expense_analysis, "total_income")
        assert hasattr(income_expense_analysis, "total_expenses")
        assert hasattr(income_expense_analysis, "expense_breakdown")

        # Verify expense_breakdown contains CategoryExpense objects
        breakdown = income_expense_analysis.expense_breakdown
        assert isinstance(breakdown, list)

        if breakdown:  # Only test if we have data
            category = breakdown[0]
            assert isinstance(category, CategoryExpense)
            assert hasattr(category, "category_name")

    async def test_savings_recommendations_compatibility(self, services, date_range):
        """Test that savings recommendations work with CategoryExpense objects."""
        savings_service = services["savings"]

        # This should not raise any AttributeError about category_name
        recommendations_data = await savings_service.get_savings_recommendations(
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            target_savings_rate=20.0,
        )

        # Verify structure
        assert isinstance(recommendations_data, dict)
        assert "current_state" in recommendations_data
        assert "recommendations" in recommendations_data

        # Verify it can be converted to Pydantic model
        response = SavingsOptimizationResponse(**recommendations_data)
        assert response is not None

    async def test_category_trends_compatibility(self, services):
        """Test that category trends analysis works with CategoryExpense objects."""
        trend_service = services["trend"]

        # This should not raise any AttributeError about category_name
        trend_data = await trend_service.analyze_category_trends(months=6, top_n=5)

        # Verify structure
        assert isinstance(trend_data, dict)
        assert "category_trends" in trend_data
        assert "period" in trend_data

        # Verify it can be converted to Pydantic model
        response = CategoryTrendsResponse(**trend_data)
        assert response is not None

    async def test_spending_trends_compatibility(self, services):
        """Test that spending trends analysis works correctly."""
        trend_service = services["trend"]

        trend_data = await trend_service.analyze_spending_trends(months=6)

        # Verify structure
        assert isinstance(trend_data, dict)
        assert "monthly_data" in trend_data
        assert "statistics" in trend_data

        # Verify it can be converted to Pydantic model
        response = SpendingTrendResponse(**trend_data)
        assert response is not None

    async def test_income_expense_trends_pydantic_compatibility(self, services):
        """Test that income vs expense trends have all required Pydantic fields."""
        trend_service = services["trend"]

        trend_data = await trend_service.analyze_income_vs_expense_trends(months=6)

        # Verify structure
        assert isinstance(trend_data, dict)
        assert "trends" in trend_data
        assert "monthly_data" in trend_data

        # Verify trends structure has all required fields
        trends = trend_data["trends"]
        assert "income" in trends
        assert "expenses" in trends
        assert "savings_rate" in trends

        # Verify savings_rate has all required Pydantic fields
        savings_rate_trend = trends["savings_rate"]
        assert "direction" in savings_rate_trend
        assert "growth_rate" in savings_rate_trend  # This was missing before
        assert "stability" in savings_rate_trend  # This was missing before
        assert "average" in savings_rate_trend
        assert "improving" in savings_rate_trend

        # Verify it can be converted to Pydantic model without validation errors
        response = IncomeVsExpenseTrendsResponse(**trend_data)
        assert response is not None

    async def test_all_services_integration_smoke_test(self, services, date_range):
        """Smoke test that exercises all services to catch basic integration issues."""
        transaction_service = services["transaction"]
        savings_service = services["savings"]
        trend_service = services["trend"]

        # Test transaction service
        transactions = await transaction_service.get_transactions(
            start_date=date_range.start_date, end_date=date_range.end_date, limit=10
        )
        assert isinstance(transactions, list)

        expense_summary = await transaction_service.get_expense_summary(
            start_date=date_range.start_date, end_date=date_range.end_date
        )
        assert isinstance(expense_summary, dict)

        income_expense = await transaction_service.get_income_vs_expense(
            start_date=date_range.start_date, end_date=date_range.end_date
        )
        assert income_expense is not None

        # Test savings service
        savings_recs = await savings_service.get_savings_recommendations(
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            target_savings_rate=20.0,
        )
        assert isinstance(savings_recs, dict)

        # Test trend service
        spending_trends = await trend_service.analyze_spending_trends(months=3)
        assert isinstance(spending_trends, dict)

        category_trends = await trend_service.analyze_category_trends(months=3, top_n=3)
        assert isinstance(category_trends, dict)

        income_expense_trends = await trend_service.analyze_income_vs_expense_trends(
            months=3
        )
        assert isinstance(income_expense_trends, dict)

    async def test_data_structure_consistency(self, services, date_range):
        """Test that data structures are consistent across different service calls."""
        transaction_service = services["transaction"]

        # Get expense summary from transaction service
        expense_summary = await transaction_service.get_expense_summary(
            start_date=date_range.start_date, end_date=date_range.end_date
        )

        # Get income vs expense analysis
        income_expense = await transaction_service.get_income_vs_expense(
            start_date=date_range.start_date, end_date=date_range.end_date
        )

        # Both should return CategoryExpense objects in their breakdowns
        expense_categories = expense_summary["category_breakdown"]
        income_expense_categories = income_expense.expense_breakdown

        if expense_categories and income_expense_categories:
            # Both should be CategoryExpense objects with same structure
            exp_cat = expense_categories[0]
            inc_exp_cat = income_expense_categories[0]

            assert type(exp_cat) is type(inc_exp_cat)
            assert isinstance(exp_cat, CategoryExpense)
            assert isinstance(inc_exp_cat, CategoryExpense)

            # Both should have the same required attributes
            required_attrs = [
                "category_name",
                "total_amount",
                "transaction_count",
                "average_amount",
                "percentage_of_total",
            ]

            for attr in required_attrs:
                assert hasattr(exp_cat, attr)
                assert hasattr(inc_exp_cat, attr)
