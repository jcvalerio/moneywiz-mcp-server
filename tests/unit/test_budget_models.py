"""Unit tests for budget models."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from moneywiz_mcp_server.models.budget import (
    BudgetAnalysisResponse,
    BudgetCategoryBreakdown,
    BudgetListResponse,
    BudgetModel,
    BudgetPeriod,
    BudgetResponse,
    BudgetStatus,
    BudgetVsActualItem,
    BudgetVsActualResponse,
)
from moneywiz_mcp_server.models.currency_types import CurrencyAmounts


class TestBudgetModel:
    """Test cases for BudgetModel."""

    @pytest.fixture
    def sample_budget(self):
        """Create a sample budget for testing."""
        return BudgetModel(
            id="123",
            name="Groceries",
            categories=["Food", "Groceries"],
            budget_amount=Decimal("500.00"),
            currency="USD",
            period=BudgetPeriod.MONTHLY,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            spent_amount=Decimal("350.00"),
            remaining_amount=Decimal("150.00"),
            percentage_used=70.0,
            status=BudgetStatus.ON_TRACK,
            is_repeatable=True,
            is_active=True,
            linked_accounts=["Checking Account"],
            transaction_count=15,
            created_date=datetime(2024, 1, 1, 10, 0, 0),
            database_id=123,
            entity_type=18,
        )

    def test_budget_model_creation(self, sample_budget):
        """Test that BudgetModel can be created with all fields."""
        assert sample_budget.id == "123"
        assert sample_budget.name == "Groceries"
        assert sample_budget.budget_amount == Decimal("500.00")
        assert sample_budget.spent_amount == Decimal("350.00")
        assert sample_budget.status == BudgetStatus.ON_TRACK

    def test_budget_commitment_type_ongoing(self, sample_budget):
        """Test commitment_type property for repeatable budget."""
        assert sample_budget.commitment_type == "ongoing"

    def test_budget_commitment_type_finite(self, sample_budget):
        """Test commitment_type property for non-repeatable budget."""
        sample_budget.is_repeatable = False
        assert sample_budget.commitment_type == "finite"

    def test_calculate_status_on_track(self, sample_budget):
        """Test status calculation for on track budget."""
        sample_budget.percentage_used = 50.0
        assert sample_budget.calculate_status() == BudgetStatus.ON_TRACK

    def test_calculate_status_at_risk(self, sample_budget):
        """Test status calculation for at risk budget."""
        sample_budget.percentage_used = 85.0
        assert sample_budget.calculate_status() == BudgetStatus.AT_RISK

    def test_calculate_status_over_budget(self, sample_budget):
        """Test status calculation for over budget."""
        sample_budget.percentage_used = 110.0
        assert sample_budget.calculate_status() == BudgetStatus.OVER_BUDGET

    def test_budget_with_no_categories(self):
        """Test budget with empty categories list."""
        budget = BudgetModel(
            id="456",
            budget_amount=Decimal("100.00"),
            currency="USD",
            period=BudgetPeriod.MONTHLY,
        )
        assert budget.categories == []
        assert budget.name is None

    def test_budget_default_values(self):
        """Test that default values are set correctly."""
        budget = BudgetModel(
            id="789",
            budget_amount=Decimal("200.00"),
            currency="USD",
            period=BudgetPeriod.MONTHLY,
        )
        assert budget.spent_amount == Decimal("0")
        assert budget.remaining_amount == Decimal("0")
        assert budget.percentage_used == 0.0
        assert budget.status == BudgetStatus.ON_TRACK
        assert budget.is_repeatable is True
        assert budget.is_active is True


class TestBudgetPeriod:
    """Test cases for BudgetPeriod enum."""

    def test_budget_period_values(self):
        """Test all BudgetPeriod enum values."""
        assert BudgetPeriod.DAILY.value == "daily"
        assert BudgetPeriod.WEEKLY.value == "weekly"
        assert BudgetPeriod.MONTHLY.value == "monthly"
        assert BudgetPeriod.YEARLY.value == "yearly"
        assert BudgetPeriod.CUSTOM.value == "custom"


class TestBudgetStatus:
    """Test cases for BudgetStatus enum."""

    def test_budget_status_values(self):
        """Test all BudgetStatus enum values."""
        assert BudgetStatus.ON_TRACK.value == "on_track"
        assert BudgetStatus.AT_RISK.value == "at_risk"
        assert BudgetStatus.OVER_BUDGET.value == "over_budget"


class TestBudgetResponse:
    """Test cases for BudgetResponse."""

    def test_budget_response_creation(self):
        """Test that BudgetResponse can be created."""
        response = BudgetResponse(
            id="123",
            name="Groceries",
            categories=["Food"],
            budget_amount=500.0,
            currency="USD",
            period="monthly",
            spent_amount=350.0,
            remaining_amount=150.0,
            percentage_used=70.0,
            status="on_track",
            is_repeatable=True,
            is_active=True,
        )
        assert response.id == "123"
        assert response.budget_amount == 500.0


class TestBudgetListResponse:
    """Test cases for BudgetListResponse."""

    def test_budget_list_response(self):
        """Test BudgetListResponse creation."""
        response = BudgetListResponse(
            budgets=[],
            total_count=0,
            filters_applied={"period": "monthly"},
            summary={"on_track": 5},
        )
        assert response.total_count == 0
        assert response.filters_applied["period"] == "monthly"


class TestBudgetAnalysisResponse:
    """Test cases for BudgetAnalysisResponse."""

    def test_budget_analysis_response(self):
        """Test BudgetAnalysisResponse creation."""
        response = BudgetAnalysisResponse(
            analysis_period="current_month",
            total_budgeted=CurrencyAmounts({"USD": Decimal("1000")}),
            total_spent=CurrencyAmounts({"USD": Decimal("700")}),
            total_remaining=CurrencyAmounts({"USD": Decimal("300")}),
            overall_percentage_used=70.0,
            overall_status="on_track",
            budgets_on_track=8,
            budgets_at_risk=1,
            budgets_over=1,
            recommendations=["Keep up the good work!"],
        )
        assert response.overall_percentage_used == 70.0
        assert response.budgets_on_track == 8


class TestBudgetCategoryBreakdown:
    """Test cases for BudgetCategoryBreakdown."""

    def test_category_breakdown(self):
        """Test BudgetCategoryBreakdown creation."""
        breakdown = BudgetCategoryBreakdown(
            category="Food",
            budget_amount=500.0,
            spent_amount=350.0,
            remaining_amount=150.0,
            percentage_used=70.0,
            status="on_track",
            transaction_count=15,
        )
        assert breakdown.category == "Food"
        assert breakdown.percentage_used == 70.0


class TestBudgetVsActualItem:
    """Test cases for BudgetVsActualItem."""

    def test_vs_actual_item(self):
        """Test BudgetVsActualItem creation."""
        item = BudgetVsActualItem(
            category="Entertainment",
            budgeted=200.0,
            actual=250.0,
            variance=-50.0,
            variance_percentage=-25.0,
            status="over_budget",
        )
        assert item.variance == -50.0
        assert item.status == "over_budget"


class TestBudgetVsActualResponse:
    """Test cases for BudgetVsActualResponse."""

    def test_vs_actual_response(self):
        """Test BudgetVsActualResponse creation."""
        response = BudgetVsActualResponse(
            period="current_month",
            total_budgeted=CurrencyAmounts({"USD": Decimal("1000")}),
            total_actual=CurrencyAmounts({"USD": Decimal("900")}),
            total_variance=CurrencyAmounts({"USD": Decimal("100")}),
            items=[],
            summary={"under_budget": 5},
        )
        assert response.period == "current_month"
