"""Analytics result models for MoneyWiz MCP Server."""

from dataclasses import dataclass
from decimal import Decimal

from typing_extensions import TypedDict

from .currency_types import CurrencyAmounts
from .transaction import DateRange


class MonthlyAverageData(TypedDict):
    """TypedDict for monthly average data structure."""

    income: dict[str, Decimal]  # currency -> amount
    expenses: dict[str, Decimal]  # currency -> amount


class MonthlyTrendData(TypedDict):
    """TypedDict for monthly trend data points."""

    month: str  # "2024-01"
    income: Decimal
    expenses: Decimal
    savings: Decimal


class PredictionData(TypedDict):
    """TypedDict for trend predictions."""

    month: str  # "2024-04"
    predicted_income: Decimal
    predicted_expenses: Decimal
    predicted_savings: Decimal
    confidence_score: float  # 0.0-1.0


@dataclass
class CategoryExpense:
    """Expense data for a specific category with Decimal precision."""

    category_name: str
    category_id: int | None
    total_amount: Decimal
    transaction_count: int
    average_amount: Decimal
    percentage_of_total: Decimal  # Use Decimal for precision
    # Multi-currency attributes (added dynamically in transaction service)
    amounts_by_currency: dict[str, Decimal] | None = None
    transaction_counts_by_currency: dict[str, int] | None = None
    average_amounts_by_currency: dict[str, Decimal] | None = None
    percentage_within_currency: dict[str, Decimal] | None = None


@dataclass
class CategoryImpact:
    """Analysis of a category's financial impact with Decimal precision."""

    category_name: str
    category_id: int | None
    total_amount: Decimal
    transaction_count: int
    impact_score: Decimal  # 0-100 scale
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
    """A specific recommendation for increasing savings with Decimal precision."""

    category_name: str
    current_spending: Decimal
    potential_reduction: Decimal
    confidence: Decimal  # 0-1 scale
    recommendation_text: str
    priority: str  # "high", "medium", "low"


@dataclass
class SpendingPatterns:
    """Analysis of spending patterns over time with Decimal precision."""

    monthly_average: Decimal
    trend_direction: str  # "increasing", "decreasing", "stable"
    volatility_score: Decimal  # 0-1 scale (0=stable, 1=highly volatile)
    peak_months: list[str]  # Months with highest spending
    seasonal_patterns: dict[str, Decimal]  # Month -> spending multiplier


@dataclass
class SavingsAnalysis:
    """Analysis of savings potential and recommendations with Decimal precision."""

    current_savings_rate: Decimal  # Percentage of income saved
    potential_savings: Decimal
    recommendations: list[SavingsRecommendation]
    spending_patterns: SpendingPatterns
    analysis_period: DateRange
    currency: str


@dataclass
class IncomeExpenseAnalysis:
    """Analysis of income vs expenses using CurrencyAmounts for type safety."""

    total_income: CurrencyAmounts
    total_expenses: CurrencyAmounts
    net_savings: CurrencyAmounts
    savings_rate: dict[str, Decimal]  # currency -> percentage (Decimal for precision)
    income_breakdown: list[CategoryExpense]
    expense_breakdown: list[CategoryExpense]
    analysis_period: DateRange
    currencies_found: list[str]
    primary_currency: str
    monthly_averages: dict[str, MonthlyAverageData]  # month -> income/expense data


@dataclass
class TrendAnalysis:
    """Analysis of spending and income trends over time with Decimal precision."""

    income_trend: str  # "increasing", "decreasing", "stable"
    expense_trend: str  # "increasing", "decreasing", "stable"
    savings_trend: str  # "improving", "declining", "stable"
    monthly_data: list[MonthlyTrendData]  # Monthly trend data points
    growth_rates: dict[str, Decimal]  # {"income": 0.05, "expenses": 0.03}
    analysis_period: DateRange
    predictions: list[PredictionData]  # Next 3 months predictions
