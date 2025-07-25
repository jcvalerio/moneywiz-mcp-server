"""Pydantic response models for savings and trend analysis."""

from typing import Any

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class FixedVsVariableData(TypedDict, total=False):
    """TypedDict for fixed vs variable expense insights."""

    fixed_percentage: float
    variable_percentage: float
    top_fixed_categories: list[str]
    optimization_opportunities: list[str]


class SpendingPatternsData(TypedDict, total=False):
    """TypedDict for spending pattern insights."""

    trend: str  # "increasing", "decreasing", "stable"
    volatility: float  # 0.0-1.0
    peak_periods: list[str]
    recommendations: list[str]
    patterns_detected: list[str]  # Add this field that the service actually provides


class CategoryAnalysisData(TypedDict, total=False):
    """TypedDict for category-based insights."""

    highest_impact_categories: list[str]
    growth_categories: list[str]
    reduction_opportunities: list[str]
    concentration: dict[str, Any]  # Add this field that the service actually provides


class AnalysisPeriodData(TypedDict):
    """TypedDict for analysis period details."""

    start_date: str
    end_date: str
    duration_months: int
    data_quality: str


class VisualizationData(TypedDict, total=False):
    """TypedDict for visualization data."""

    chart_type: str
    data_points: list[dict[str, float]]
    labels: list[str]
    line_chart: dict[str, Any]  # Add this field that the service actually provides
    bar_chart: dict[str, Any]  # Add this field that the service actually provides


class SavingsRecommendation(BaseModel):
    """Model for a savings recommendation."""

    type: str = Field(..., description="Type of recommendation")
    priority: str = Field(..., description="Priority level (high/medium/low)")
    priority_score: float | None = Field(None, description="Numeric priority score")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    impact: str = Field(..., description="Expected financial impact")
    difficulty: str = Field(..., description="Implementation difficulty")
    category: str | None = Field(None, description="Related category")
    tips: list[str] | None = Field(None, description="Actionable tips")


class CurrentSavingsState(BaseModel):
    """Model for current savings state."""

    savings_rate: float = Field(..., description="Current savings rate percentage")
    monthly_savings: float = Field(..., description="Average monthly savings amount")
    total_income: float = Field(..., description="Total income in period")
    total_expenses: float = Field(..., description="Total expenses in period")


class TargetSavingsState(BaseModel):
    """Model for target savings state."""

    target_savings_rate: float = Field(
        ..., description="Target savings rate percentage"
    )
    projected_savings_rate: float = Field(
        ..., description="Projected rate with recommendations"
    )
    potential_monthly_savings: float = Field(
        ..., description="Potential additional monthly savings"
    )
    needed_expense_reduction: float = Field(
        ..., description="Required expense reduction to meet target"
    )


class SavingsInsights(BaseModel):
    """Model for savings insights."""

    fixed_vs_variable: FixedVsVariableData = Field(
        ..., description="Fixed vs variable expense insights"
    )
    spending_patterns: SpendingPatternsData = Field(
        ..., description="Spending pattern insights"
    )
    category_analysis: CategoryAnalysisData = Field(
        ..., description="Category-based insights"
    )


class SavingsOptimizationResponse(BaseModel):
    """Response model for savings optimization recommendations."""

    current_state: CurrentSavingsState = Field(
        ..., description="Current financial state"
    )
    target_state: TargetSavingsState = Field(..., description="Target financial state")
    recommendations: list[SavingsRecommendation] = Field(
        ..., description="Prioritized recommendations"
    )
    insights: SavingsInsights = Field(..., description="Analysis insights")


class TrendStatistics(BaseModel):
    """Model for trend statistics."""

    average_monthly: float = Field(..., description="Average monthly amount")
    median_monthly: float = Field(..., description="Median monthly amount")
    std_deviation: float = Field(..., description="Standard deviation")
    trend_direction: str = Field(
        ..., description="Trend direction (increasing/stable/decreasing)"
    )
    trend_strength: str = Field(
        ..., description="Trend strength (strong/moderate/weak)"
    )
    growth_rate: float = Field(..., description="Monthly growth rate percentage")


class MonthlyTrendData(BaseModel):
    """Model for monthly trend data."""

    month: str = Field(..., description="Month (YYYY-MM format)")
    total_expenses: float = Field(..., description="Total expenses for the month")
    transaction_count: int = Field(..., description="Number of transactions")
    average_transaction: float = Field(..., description="Average transaction amount")


class TrendProjection(BaseModel):
    """Model for trend projections."""

    month: str = Field(..., description="Projected month (YYYY-MM format)")
    projected_amount: float = Field(..., description="Projected amount")
    confidence: str = Field(..., description="Confidence level (high/medium/low)")


class TrendInsight(BaseModel):
    """Model for trend insights."""

    type: str = Field(..., description="Insight type (warning/positive/info)")
    title: str = Field(..., description="Insight title")
    description: str = Field(..., description="Detailed description")
    priority: str = Field(..., description="Priority level")


class SpendingTrendResponse(BaseModel):
    """Response model for spending trend analysis."""

    period: AnalysisPeriodData = Field(..., description="Analysis period details")
    monthly_data: list[MonthlyTrendData] = Field(..., description="Monthly breakdown")
    statistics: TrendStatistics = Field(..., description="Trend statistics")
    insights: list[TrendInsight] = Field(..., description="Trend insights")
    projections: list[TrendProjection] = Field(..., description="Future projections")
    visualizations: VisualizationData = Field(..., description="Visualization data")


class CategoryTrend(BaseModel):
    """Model for category trend data."""

    category: str = Field(..., description="Category name")
    total_spent: float = Field(..., description="Total spent in period")
    percentage_of_total: float = Field(..., description="Percentage of total expenses")
    trend: str = Field(..., description="Trend direction")
    growth_rate: float = Field(..., description="Growth rate percentage")
    monthly_average: float = Field(..., description="Monthly average")
    insights: list[TrendInsight] = Field(..., description="Category-specific insights")


class CategoryTrendsResponse(BaseModel):
    """Response model for category trends analysis."""

    period: AnalysisPeriodData = Field(..., description="Analysis period details")
    category_trends: list[CategoryTrend] = Field(..., description="Trends by category")
    overall_insights: list[TrendInsight] = Field(..., description="Overall insights")


class IncomeExpenseTrend(BaseModel):
    """Model for income/expense trend data."""

    direction: str = Field(..., description="Trend direction")
    growth_rate: float = Field(..., description="Growth rate percentage")
    stability: str = Field(..., description="Stability level")
    average: float | None = Field(None, description="Average value")
    improving: bool | None = Field(None, description="Whether trend is improving")


class MonthlyIncomeExpenseData(BaseModel):
    """Model for monthly income vs expense data."""

    month: str = Field(..., description="Month (YYYY-MM format)")
    income: float = Field(..., description="Total income")
    expenses: float = Field(..., description="Total expenses")
    net_savings: float = Field(..., description="Net savings")
    savings_rate: float = Field(..., description="Savings rate percentage")


class IncomeVsExpenseTrendsResponse(BaseModel):
    """Response model for income vs expense trends."""

    period: AnalysisPeriodData = Field(..., description="Analysis period")
    monthly_data: list[MonthlyIncomeExpenseData] = Field(
        ..., description="Monthly breakdown"
    )
    trends: dict[str, IncomeExpenseTrend] = Field(
        ..., description="Trends for income, expenses, savings"
    )
    insights: list[TrendInsight] = Field(..., description="Analysis insights")
