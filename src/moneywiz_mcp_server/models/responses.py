"""Pydantic response models for structured MCP output."""

from typing import Any

from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    """Response model for account data."""

    id: str = Field(..., description="Unique account identifier")
    name: str = Field(..., description="Account name")
    type: str = Field(..., description="Account type (checking, savings, etc.)")
    balance: str = Field(..., description="Formatted current balance with currency")
    currency: str = Field(..., description="Account currency code")
    entity_type: str = Field(..., description="MoneyWiz entity type")
    last_updated: str = Field(..., description="Last update timestamp")
    archived: bool = Field(..., description="Whether account is archived/hidden")


class AccountListResponse(BaseModel):
    """Response model for list of accounts."""

    accounts: list[AccountResponse] = Field(..., description="List of accounts")
    total_count: int = Field(..., description="Total number of accounts")
    filters_applied: dict[str, Any] = Field(
        default_factory=dict, description="Applied filters"
    )


class AccountDetailResponse(AccountResponse):
    """Response model for detailed account information."""

    created_date: str = Field(..., description="Account creation date")
    institution: str = Field(..., description="Financial institution")
    account_info: str = Field(..., description="Additional account information")
    last_four_digits: str = Field(..., description="Last four digits of account number")
    recent_transactions: list[dict[str, Any]] = Field(
        default_factory=list, description="Recent transactions"
    )


class TransactionResponse(BaseModel):
    """Response model for transaction data."""

    id: str = Field(..., description="Transaction ID")
    date: str = Field(..., description="Transaction date (ISO format)")
    description: str = Field(..., description="Transaction description")
    amount: str = Field(..., description="Formatted amount with currency")
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
    filters_applied: dict[str, Any] = Field(
        default_factory=dict, description="Applied filters"
    )


class CategoryExpenseResponse(BaseModel):
    """Response model for category expense data."""

    rank: int = Field(..., description="Category rank by expense amount")
    category: str = Field(..., description="Category name")
    total_amount: str = Field(..., description="Total amount spent in category")
    transaction_count: int = Field(
        ..., description="Number of transactions in category"
    )
    average_amount: str = Field(..., description="Average amount per transaction")
    percentage_of_total: float = Field(..., description="Percentage of total expenses")
    impact_level: str = Field(..., description="Impact level (high/medium/low)")


class ExpenseAnalysisResponse(BaseModel):
    """Response model for expense analysis by category."""

    analysis_period: str = Field(..., description="Time period analyzed")
    total_expenses: str = Field(..., description="Total expenses in period")
    currency: str = Field(..., description="Currency used")
    top_categories: list[CategoryExpenseResponse] = Field(
        ..., description="Top expense categories"
    )
    summary: dict[str, Any] = Field(..., description="Analysis summary statistics")
    insights: dict[str, Any] | None = Field(
        None, description="Analysis insights and recommendations"
    )


class FinancialOverviewResponse(BaseModel):
    """Response model for financial overview data."""

    total_income: str = Field(..., description="Total income in period")
    total_expenses: str = Field(..., description="Total expenses in period")
    net_savings: str = Field(..., description="Net savings (income - expenses)")
    savings_rate: str = Field(..., description="Savings rate as percentage")
    currency: str = Field(..., description="Currency used")


class SavingsAnalysisResponse(BaseModel):
    """Response model for savings analysis."""

    status: str = Field(..., description="Savings status (positive/negative)")
    monthly_savings: str = Field(..., description="Average monthly savings")
    recommendations: list[str] = Field(..., description="Savings recommendations")


class IncomeVsExpensesResponse(BaseModel):
    """Response model for income vs expenses analysis."""

    analysis_period: str = Field(..., description="Time period analyzed")
    financial_overview: FinancialOverviewResponse = Field(
        ..., description="Financial overview"
    )
    expense_breakdown: list[dict[str, Any]] = Field(
        ..., description="Top expense categories"
    )
    savings_analysis: SavingsAnalysisResponse = Field(
        ..., description="Savings analysis"
    )


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
