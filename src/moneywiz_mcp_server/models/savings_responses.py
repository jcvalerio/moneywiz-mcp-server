"""Pydantic response models for savings and trend analysis."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SavingsRecommendation(BaseModel):
    """Model for a savings recommendation."""
    type: str = Field(..., description="Type of recommendation")
    priority: str = Field(..., description="Priority level (high/medium/low)")
    priority_score: Optional[float] = Field(None, description="Numeric priority score")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    impact: str = Field(..., description="Expected financial impact")
    difficulty: str = Field(..., description="Implementation difficulty")
    category: Optional[str] = Field(None, description="Related category")
    tips: Optional[List[str]] = Field(None, description="Actionable tips")


class CurrentSavingsState(BaseModel):
    """Model for current savings state."""
    savings_rate: float = Field(..., description="Current savings rate percentage")
    monthly_savings: float = Field(..., description="Average monthly savings amount")
    total_income: float = Field(..., description="Total income in period")
    total_expenses: float = Field(..., description="Total expenses in period")


class TargetSavingsState(BaseModel):
    """Model for target savings state."""
    target_savings_rate: float = Field(..., description="Target savings rate percentage")
    projected_savings_rate: float = Field(..., description="Projected rate with recommendations")
    potential_monthly_savings: float = Field(..., description="Potential additional monthly savings")
    needed_expense_reduction: float = Field(..., description="Required expense reduction to meet target")


class SavingsInsights(BaseModel):
    """Model for savings insights."""
    fixed_vs_variable: Dict[str, Any] = Field(..., description="Fixed vs variable expense insights")
    spending_patterns: Dict[str, Any] = Field(..., description="Spending pattern insights")
    category_analysis: Dict[str, Any] = Field(..., description="Category-based insights")


class SavingsOptimizationResponse(BaseModel):
    """Response model for savings optimization recommendations."""
    current_state: CurrentSavingsState = Field(..., description="Current financial state")
    target_state: TargetSavingsState = Field(..., description="Target financial state")
    recommendations: List[SavingsRecommendation] = Field(..., description="Prioritized recommendations")
    insights: SavingsInsights = Field(..., description="Analysis insights")


class TrendStatistics(BaseModel):
    """Model for trend statistics."""
    average_monthly: float = Field(..., description="Average monthly amount")
    median_monthly: float = Field(..., description="Median monthly amount")
    std_deviation: float = Field(..., description="Standard deviation")
    trend_direction: str = Field(..., description="Trend direction (increasing/stable/decreasing)")
    trend_strength: str = Field(..., description="Trend strength (strong/moderate/weak)")
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
    period: Dict[str, Any] = Field(..., description="Analysis period details")
    monthly_data: List[MonthlyTrendData] = Field(..., description="Monthly breakdown")
    statistics: TrendStatistics = Field(..., description="Trend statistics")
    insights: List[TrendInsight] = Field(..., description="Trend insights")
    projections: List[TrendProjection] = Field(..., description="Future projections")
    visualizations: Dict[str, Any] = Field(..., description="Visualization data")


class CategoryTrend(BaseModel):
    """Model for category trend data."""
    category: str = Field(..., description="Category name")
    total_spent: float = Field(..., description="Total spent in period")
    percentage_of_total: float = Field(..., description="Percentage of total expenses")
    trend: str = Field(..., description="Trend direction")
    growth_rate: float = Field(..., description="Growth rate percentage")
    monthly_average: float = Field(..., description="Monthly average")
    insights: List[TrendInsight] = Field(..., description="Category-specific insights")


class CategoryTrendsResponse(BaseModel):
    """Response model for category trends analysis."""
    period: Dict[str, Any] = Field(..., description="Analysis period details")
    category_trends: List[CategoryTrend] = Field(..., description="Trends by category")
    overall_insights: List[TrendInsight] = Field(..., description="Overall insights")


class IncomeExpenseTrend(BaseModel):
    """Model for income/expense trend data."""
    direction: str = Field(..., description="Trend direction")
    growth_rate: float = Field(..., description="Growth rate percentage")
    stability: str = Field(..., description="Stability level")
    average: Optional[float] = Field(None, description="Average value")
    improving: Optional[bool] = Field(None, description="Whether trend is improving")


class MonthlyIncomeExpenseData(BaseModel):
    """Model for monthly income vs expense data."""
    month: str = Field(..., description="Month (YYYY-MM format)")
    income: float = Field(..., description="Total income")
    expenses: float = Field(..., description="Total expenses")
    net_savings: float = Field(..., description="Net savings")
    savings_rate: float = Field(..., description="Savings rate percentage")


class IncomeVsExpenseTrendsResponse(BaseModel):
    """Response model for income vs expense trends."""
    period: Dict[str, Any] = Field(..., description="Analysis period")
    monthly_data: List[MonthlyIncomeExpenseData] = Field(..., description="Monthly breakdown")
    trends: Dict[str, IncomeExpenseTrend] = Field(..., description="Trends for income, expenses, savings")
    insights: List[TrendInsight] = Field(..., description="Analysis insights")