"""Analytics result models for MoneyWiz MCP Server."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .transaction import DateRange


@dataclass
class CategoryExpense:
    """Expense data for a specific category."""

    category_name: str
    category_id: int | None
    total_amount: Decimal
    transaction_count: int
    average_amount: Decimal
    percentage_of_total: float


@dataclass
class CategoryImpact:
    """Analysis of a category's financial impact."""

    category_name: str
    category_id: int | None
    total_amount: Decimal
    transaction_count: int
    impact_score: float  # 0-100 scale
    trend: str  # "increasing", "decreasing", "stable"
    recommendation: str


@dataclass
class CategoryAnalysisResult:
    """Result of category-based expense analysis."""

    total_expenses: Decimal
    category_breakdown: list[CategoryExpense]
    top_categories: list[CategoryImpact]
    analysis_period: DateRange
    currency: str
    analysis_date: str  # ISO format


@dataclass
class SavingsRecommendation:
    """A specific recommendation for increasing savings."""

    category_name: str
    current_spending: Decimal
    potential_reduction: Decimal
    confidence: float  # 0-1 scale
    recommendation_text: str
    priority: str  # "high", "medium", "low"


@dataclass
class SpendingPatterns:
    """Analysis of spending patterns over time."""

    monthly_average: Decimal
    trend_direction: str  # "increasing", "decreasing", "stable"
    volatility_score: float  # 0-1 scale (0=stable, 1=highly volatile)
    peak_months: list[str]  # Months with highest spending
    seasonal_patterns: dict[str, float]  # Month -> spending multiplier


@dataclass
class SavingsAnalysis:
    """Analysis of savings potential and recommendations."""

    current_savings_rate: float  # Percentage of income saved
    potential_savings: Decimal
    recommendations: list[SavingsRecommendation]
    spending_patterns: SpendingPatterns
    analysis_period: DateRange
    currency: str


@dataclass
class IncomeExpenseAnalysis:
    """Analysis of income vs expenses."""

    total_income: Decimal
    total_expenses: Decimal
    net_savings: Decimal
    savings_rate: float  # Percentage
    income_breakdown: list[CategoryExpense]
    expense_breakdown: list[CategoryExpense]
    analysis_period: DateRange
    currency: str
    monthly_averages: dict[str, Any]  # month -> {"income": amount, "expenses": amount}


@dataclass
class TrendAnalysis:
    """Analysis of spending and income trends over time."""

    income_trend: str  # "increasing", "decreasing", "stable"
    expense_trend: str  # "increasing", "decreasing", "stable"
    savings_trend: str  # "improving", "declining", "stable"
    monthly_data: list[
        dict[str, Any]
    ]  # [{"month": "2024-01", "income": 5000, "expenses": 3000}]
    growth_rates: dict[str, float]  # {"income": 0.05, "expenses": 0.03}
    analysis_period: DateRange
    predictions: dict[str, Any]  # Next 3 months predictions
