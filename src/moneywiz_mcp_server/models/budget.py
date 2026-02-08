"""Budget models for MoneyWiz MCP Server."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .currency_types import CurrencyAmounts


class BudgetPeriod(str, Enum):
    """Budget period/frequency type."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class BudgetStatus(str, Enum):
    """Budget spending status."""

    ON_TRACK = "on_track"  # < 80% spent
    AT_RISK = "at_risk"  # 80-100% spent
    OVER_BUDGET = "over_budget"  # > 100% spent


class BudgetModel(BaseModel):
    """Internal model for budget data with full details."""

    id: str
    name: str | None = None
    categories: list[str] = Field(default_factory=list)
    budget_amount: Decimal
    currency: str = "USD"
    period: BudgetPeriod
    period_start: date | None = None
    period_end: date | None = None
    spent_amount: Decimal = Decimal("0")
    remaining_amount: Decimal = Decimal("0")
    percentage_used: float = 0.0
    status: BudgetStatus = BudgetStatus.ON_TRACK
    is_repeatable: bool = True
    is_active: bool = True
    linked_accounts: list[str] = Field(default_factory=list)
    transaction_count: int = 0
    created_date: datetime | None = None
    last_updated: datetime | None = None
    database_id: int | None = None
    entity_type: int | None = None

    @property
    def commitment_type(self) -> str:
        """Determine if budget is finite or ongoing."""
        return "ongoing" if self.is_repeatable else "finite"

    def calculate_status(self) -> BudgetStatus:
        """Calculate budget status based on spending percentage."""
        if self.percentage_used >= 100:
            return BudgetStatus.OVER_BUDGET
        elif self.percentage_used >= 80:
            return BudgetStatus.AT_RISK
        return BudgetStatus.ON_TRACK


class BudgetResponse(BaseModel):
    """API response model for a single budget."""

    id: str
    name: str | None = None
    categories: list[str] = Field(default_factory=list)
    budget_amount: float
    currency: str
    period: str
    period_start: str | None = None
    period_end: str | None = None
    spent_amount: float
    remaining_amount: float
    percentage_used: float
    status: str
    is_repeatable: bool
    is_active: bool
    linked_accounts: list[str] = Field(default_factory=list)
    transaction_count: int = 0


class BudgetListResponse(BaseModel):
    """Response model for list of budgets."""

    budgets: list[BudgetResponse]
    total_count: int
    filters_applied: dict[str, Any]
    summary: dict[str, Any] = Field(default_factory=dict)


class BudgetCategoryBreakdown(BaseModel):
    """Breakdown of spending by category within a budget."""

    category: str
    budget_amount: float
    spent_amount: float
    remaining_amount: float
    percentage_used: float
    status: str
    transaction_count: int


class BudgetAnalysisResponse(BaseModel):
    """Response model for budget analysis."""

    analysis_period: str
    total_budgeted: CurrencyAmounts
    total_spent: CurrencyAmounts
    total_remaining: CurrencyAmounts
    overall_percentage_used: float
    overall_status: str
    budgets_on_track: int
    budgets_at_risk: int
    budgets_over: int
    category_breakdown: list[BudgetCategoryBreakdown] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class BudgetVsActualItem(BaseModel):
    """Single budget vs actual comparison item."""

    category: str
    budgeted: float
    actual: float
    variance: float
    variance_percentage: float
    status: str


class BudgetVsActualResponse(BaseModel):
    """Response model for budget vs actual comparison."""

    period: str
    total_budgeted: CurrencyAmounts
    total_actual: CurrencyAmounts
    total_variance: CurrencyAmounts
    items: list[BudgetVsActualItem] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
