"""Pydantic response models for structured MCP output."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from .base import BaseAnalysisResponse, BaseCurrencyResponse, FilterData
from .currency_types import CurrencyAmounts


class RecentTransactionData(BaseModel):
    """Model for recent transaction data in account details."""

    id: str = Field(..., description="Transaction ID")
    date: str = Field(..., description="Transaction date (ISO format)")
    description: str = Field(..., description="Transaction description")
    amount: float = Field(..., description="Transaction amount")
    category: str = Field(..., description="Transaction category")
    transaction_type: str = Field(..., description="Transaction type")


class AnalysisSummaryData(BaseModel):
    """Model for analysis summary statistics."""

    total_categories: int = Field(..., description="Total number of categories")
    categories_analyzed: int = Field(..., description="Number of categories analyzed")
    analysis_complete: bool = Field(..., description="Whether analysis is complete")


class AnalysisInsightsData(BaseModel):
    """Model for analysis insights and recommendations."""

    currencies_found: list[str] = Field(..., description="List of currencies found")
    multi_currency_spending: bool = Field(
        ..., description="Whether spending is multi-currency"
    )


class ExpenseBreakdownData(BaseModel):
    """Model for expense breakdown data."""

    category_name: str = Field(..., description="Category name")
    total_amount: float = Field(..., description="Total amount spent")
    percentage_of_total: float = Field(..., description="Percentage of total expenses")


class ErrorDetailsData(BaseModel):
    """Model for error details."""

    code: str | None = Field(None, description="Error code")
    context: str | None = Field(None, description="Error context")
    suggestion: str | None = Field(None, description="Suggested resolution")


class AccountResponse(BaseModel):
    """Response model for account data."""

    id: str = Field(..., description="Unique account identifier")
    name: str = Field(..., description="Account name")
    type: str = Field(..., description="Account type (checking, savings, etc.)")
    balance: float = Field(..., description="Current account balance")
    currency: str = Field(..., description="Account currency code")
    entity_type: str = Field(..., description="MoneyWiz entity type")
    last_updated: str = Field(..., description="Last update timestamp")
    archived: bool = Field(..., description="Whether account is archived/hidden")


class AccountListResponse(BaseModel):
    """Response model for list of accounts."""

    accounts: list[AccountResponse] = Field(..., description="List of accounts")
    total_count: int = Field(..., description="Total number of accounts")
    filters_applied: FilterData | dict[str, Any] = Field(
        default_factory=dict, description="Applied filters"
    )


class AccountDetailResponse(AccountResponse):
    """Response model for detailed account information."""

    created_date: str = Field(..., description="Account creation date")
    institution: str = Field(..., description="Financial institution")
    account_info: str = Field(..., description="Additional account information")
    last_four_digits: str = Field(..., description="Last four digits of account number")
    recent_transactions: list[RecentTransactionData] = Field(
        default_factory=list, description="Recent transactions"
    )


class TransactionResponse(BaseModel):
    """Response model for transaction data."""

    id: str = Field(..., description="Transaction ID")
    date: str = Field(..., description="Transaction date (ISO format)")
    description: str = Field(..., description="Transaction description")
    amount: float = Field(..., description="Transaction amount")
    category: str = Field(..., description="Transaction category")
    payee: str = Field(..., description="Transaction payee")
    account_id: str = Field(..., description="Associated account ID")
    transaction_type: str = Field(..., description="Type of transaction")
    currency: str = Field(..., description="Transaction currency")
    reconciled: bool = Field(..., description="Whether transaction is reconciled")
    notes: str | None = Field(None, description="Transaction notes")


class TransactionListResponse(BaseModel):
    """Response model for transaction search results."""

    transactions: list[TransactionResponse] = Field(
        ..., description="List of transactions"
    )
    total_count: int = Field(..., description="Total number of transactions found")
    date_range: str = Field(..., description="Date range searched")
    filters_applied: FilterData | dict[str, Any] = Field(
        default_factory=dict, description="Applied filters"
    )


class CategoryExpenseResponse(BaseCurrencyResponse):
    """Response model for category expense data with multi-currency support."""

    rank: int = Field(..., description="Category rank by expense amount")
    category: str = Field(..., description="Category name")
    currency_amounts: CurrencyAmounts = Field(
        ..., description="Total amounts spent by currency"
    )
    transaction_counts_by_currency: dict[str, int] = Field(
        ..., description="Number of transactions by currency"
    )
    average_amounts: CurrencyAmounts = Field(
        ..., description="Average amounts by currency"
    )
    percentage_within_currency: dict[str, Decimal] = Field(
        ..., description="Percentage of total expenses within each currency"
    )
    impact_level: str = Field(..., description="Impact level (high/medium/low)")


class ExpenseAnalysisResponse(BaseAnalysisResponse, BaseCurrencyResponse):
    """Response model for expense analysis by category."""

    total_expenses: CurrencyAmounts = Field(
        ..., description="Total expenses by currency"
    )
    top_categories: list[CategoryExpenseResponse] = Field(
        ..., description="Top expense categories with currency breakdown"
    )
    summary: AnalysisSummaryData = Field(..., description="Analysis summary statistics")
    insights: AnalysisInsightsData | None = Field(
        None, description="Analysis insights and recommendations"
    )


class FinancialOverviewResponse(BaseCurrencyResponse):
    """Response model for financial overview data."""

    total_income: CurrencyAmounts = Field(..., description="Total income by currency")
    total_expenses: CurrencyAmounts = Field(
        ..., description="Total expenses by currency"
    )
    net_savings: CurrencyAmounts = Field(
        ..., description="Net savings by currency (income - expenses)"
    )
    savings_rate: dict[str, Decimal] = Field(
        ..., description="Savings rate as percentage by currency"
    )
    currencies_found: list[str] = Field(
        ..., description="List of currencies found in the data"
    )
    primary_currency: str = Field(
        ..., description="Primary currency (highest activity)"
    )


class SavingsAnalysisResponse(BaseCurrencyResponse):
    """Response model for savings analysis."""

    status: str = Field(..., description="Savings status (positive/negative)")
    monthly_savings: CurrencyAmounts = Field(
        ..., description="Average monthly savings by currency"
    )
    recommendations: list[str] = Field(..., description="Savings recommendations")


class IncomeVsExpensesResponse(BaseModel):
    """Response model for income vs expenses analysis."""

    analysis_period: str = Field(..., description="Time period analyzed")
    financial_overview: FinancialOverviewResponse = Field(
        ..., description="Financial overview"
    )
    expense_breakdown: list[ExpenseBreakdownData] = Field(
        ..., description="Top expense categories"
    )
    savings_analysis: SavingsAnalysisResponse = Field(
        ..., description="Savings analysis"
    )


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    details: ErrorDetailsData | None = Field(
        None, description="Additional error details"
    )
