"""Pydantic models for scheduled transactions with occurrence tracking."""

from datetime import datetime
from decimal import Decimal
from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_serializer

from .base import ApiDateTime, BaseCurrencyResponse
from .currency_types import CurrencyAmounts
from .transaction import TransactionType


class RecurrencePattern(StrEnum):
    """Enumeration of recurrence patterns for scheduled transactions."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class RecurrenceEndCondition(StrEnum):
    """Enumeration of end conditions for scheduled transactions."""

    NEVER = "never"  # Infinite recurrence
    AFTER_OCCURRENCES = "after_occurrences"  # End after N occurrences
    ON_DATE = "on_date"  # End on specific date


class WeekendHandling(StrEnum):
    """How to handle scheduled transactions that fall on weekends."""

    SAME_DAY = "same_day"  # Execute on weekend
    NEXT_WEEKDAY = "next_weekday"  # Move to next weekday
    PREVIOUS_WEEKDAY = "previous_weekday"  # Move to previous weekday


class ScheduledTransactionModel(BaseModel):
    """Model for scheduled transaction data with occurrence tracking."""

    # Basic Transaction Information
    id: str = Field(..., description="Unique scheduled transaction identifier")
    description: str = Field(..., description="Transaction description")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Transaction currency")
    account_id: str = Field(..., description="Associated account ID")
    recipient_account_id: str | None = Field(
        None, description="Destination account ID (transfers only)"
    )
    category: str = Field(..., description="Transaction leaf category")
    category_id: int | None = Field(None, description="Transaction category ID")
    parent_category: str | None = Field(None, description="Immediate parent category")
    parent_category_id: int | None = Field(
        None, description="Immediate parent category ID"
    )
    root_category: str | None = Field(None, description="Root category")
    category_path: str | None = Field(None, description="Full category hierarchy path")
    category_hierarchy: list[str] = Field(
        default_factory=list, description="Category hierarchy from root to leaf"
    )
    payee: str = Field(..., description="Transaction payee")
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    tags: list[str] = Field(default_factory=list, description="Transaction tags")

    # Recurrence Information
    recurrence_pattern: RecurrencePattern = Field(
        ..., description="How often the transaction repeats"
    )
    recurrence_interval: int = Field(
        default=1, description="Interval between recurrences (e.g., every 2 weeks)"
    )
    next_execution_date: datetime = Field(
        ..., description="Next scheduled execution date"
    )
    weekend_handling: WeekendHandling = Field(
        default=WeekendHandling.SAME_DAY, description="How to handle weekend execution"
    )

    # Occurrence Tracking (KEY ENHANCEMENT)
    end_condition: RecurrenceEndCondition = Field(
        ..., description="How the recurrence ends"
    )
    total_occurrences: int | None = Field(
        None, description="Total planned occurrences (None if infinite)"
    )
    completed_occurrences: int = Field(
        default=0, description="Number of executions completed"
    )
    remaining_occurrences: int | None = Field(
        None, description="Remaining occurrences (None if infinite)"
    )
    final_execution_date: datetime | None = Field(
        None, description="Date of final planned execution"
    )
    is_one_time: bool = Field(
        default=False, description="Runs once, on next_execution_date"
    )

    # Planning Information
    upcoming_dates: list[datetime] = Field(
        default_factory=list,
        description="Next 6 months of scheduled execution dates",
    )
    is_active: bool = Field(default=True, description="Whether schedule is active")
    created_date: datetime = Field(..., description="When schedule was created")
    last_executed_date: datetime | None = Field(
        None, description="When last execution occurred"
    )

    # MoneyWiz Database Fields
    entity_type: int = Field(..., description="MoneyWiz Core Data entity type")
    database_id: int = Field(..., description="Internal database primary key")

    @property
    def will_end_within_period(self) -> bool:
        """Check if schedule will end within the next 6 months."""
        if self.final_execution_date is None:
            return False

        from datetime import timedelta

        six_months_from_now = datetime.now() + timedelta(days=180)
        return self.final_execution_date <= six_months_from_now

    @property
    def commitment_type(self) -> str:
        """Classify commitment type based on occurrence pattern."""
        if self.is_one_time:
            return "one_time"
        if self.end_condition == RecurrenceEndCondition.NEVER:
            return "infinite"
        elif self.remaining_occurrences and self.remaining_occurrences <= 3:
            return "ending_soon"
        else:
            return "finite"

    @property
    def urgency_level(self) -> str:
        """Determine urgency level based on active status and next execution date."""
        if not self.is_active:
            return "inactive"

        from datetime import timedelta

        days_until_next = (self.next_execution_date - datetime.now()).days

        if days_until_next <= 1:
            return "immediate"
        elif days_until_next <= 7:
            return "urgent"
        elif days_until_next <= 30:
            return "regular"
        else:
            return "future"


class CommitmentBreakdown(BaseModel):
    """Model for individual commitment in salary breakdown analysis."""

    description: str = Field(..., description="Commitment description")
    amount: Decimal = Field(..., description="Commitment amount")
    currency: str = Field(..., description="Currency code")
    category: str = Field(..., description="Expense category")
    next_date: ApiDateTime = Field(..., description="Next execution date")

    # Occurrence Intelligence (KEY FEATURE)
    remaining_payments: int | None = Field(
        None, description="Remaining payments (None if infinite)"
    )
    final_payment_date: ApiDateTime | None = Field(
        None, description="Date of final payment"
    )
    payments_in_period: int = Field(
        ..., description="Number of payments before next salary"
    )
    total_impact_in_period: Decimal = Field(
        ..., description="Total amount for the planning period"
    )

    # Status indicators
    commitment_type: str = Field(
        ..., description="Type: finite, infinite, ending_soon, one_time"
    )
    urgency_level: str = Field(..., description="Urgency: immediate, regular, ending")
    kind: str = Field(
        "expense",
        description="expense (scheduled withdrawal), debt_payment (bank -> Loan "
        "account) or savings (bank -> Investment account)",
    )


class IncomeSource(BaseModel):
    """One income stream counted in a salary breakdown, in its own currency."""

    description: str = Field(..., description="Income description")
    currency: str = Field(..., description="Currency code")
    amount_per_payment: Decimal = Field(..., description="Amount of each payment")
    payments_in_period: int = Field(..., description="Payments inside the period")
    total_in_period: Decimal = Field(..., description="Total received in the period")
    recurrence_pattern: str = Field(..., description="daily/weekly/monthly/yearly")
    recurrence_interval: int = Field(..., description="Every N pattern units")
    source: str = Field(
        ..., description="'scheduled' (MoneyWiz schedule) or 'provided' (tool input)"
    )

    @field_serializer("amount_per_payment", "total_in_period")
    def _serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class ExchangeRateUsed(BaseModel):
    """Rate used to express an amount in the display currency."""

    currency: str = Field(..., description="Currency code")
    units_per_display_currency: float = Field(
        ..., description="Units of this currency per 1 unit of the display currency"
    )
    as_of: ApiDateTime | None = Field(
        None, description="Date of the MoneyWiz transaction the rate comes from"
    )
    source: str = Field(..., description="'moneywiz' or 'provided'")


class DisplayCurrencyTotals(BaseModel):
    """Period totals converted into one currency."""

    currency: str = Field(..., description="Display currency")
    income: float = Field(..., description="Income in the period")
    commitments: float = Field(..., description="Commitments in the period")
    remaining: float = Field(..., description="Income minus commitments")


class ScheduledTransactionResponse(BaseModel):
    """Response model for scheduled transaction data."""

    id: str = Field(..., description="Scheduled transaction ID")
    description: str = Field(..., description="Transaction description")
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Transaction currency")
    category: str = Field(..., description="Transaction leaf category")
    category_id: int | None = Field(None, description="Transaction category ID")
    parent_category: str | None = Field(None, description="Immediate parent category")
    parent_category_id: int | None = Field(
        None, description="Immediate parent category ID"
    )
    root_category: str | None = Field(None, description="Root category")
    category_path: str | None = Field(None, description="Full category hierarchy path")
    category_hierarchy: list[str] = Field(
        default_factory=list, description="Category hierarchy from root to leaf"
    )
    payee: str = Field(..., description="Transaction payee")
    account_id: str = Field(..., description="Associated account ID")
    recurrence_pattern: str = Field(..., description="Recurrence pattern")
    recurrence_interval: int = Field(
        default=1,
        description="Repeats every N recurrence_pattern units "
        "(e.g. weekly with interval 2 = every 2 weeks)",
    )
    upcoming_dates: list[ApiDateTime] = Field(
        default_factory=list,
        description="Upcoming execution dates in the next 6 months (max 20)",
    )
    next_execution_date: ApiDateTime = Field(..., description="Next execution date")
    transaction_type: str = Field(..., description="Transaction type")
    tags: list[str] = Field(default_factory=list, description="Transaction tags")

    # Occurrence tracking
    end_condition: str = Field(..., description="End condition")
    total_occurrences: int | None = Field(None, description="Total planned occurrences")
    completed_occurrences: int = Field(..., description="Completed occurrences")
    remaining_occurrences: int | None = Field(None, description="Remaining occurrences")
    final_execution_date: ApiDateTime | None = Field(
        None, description="Final execution date"
    )

    is_active: bool = Field(..., description="Whether schedule is active")
    commitment_type: str = Field(
        ..., description="finite/infinite/ending_soon/one_time"
    )
    urgency_level: str = Field(..., description="immediate/regular/future")


class ScheduledTransactionListResponse(BaseModel):
    """Response model for list of scheduled transactions."""

    scheduled_transactions: list[ScheduledTransactionResponse] = Field(
        ..., description="List of scheduled transactions"
    )
    total_count: int = Field(..., description="Total number of scheduled transactions")
    filters_applied: dict[str, Any] = Field(
        default_factory=dict, description="Applied filters"
    )
    summary: dict[str, Any] = Field(
        default_factory=dict, description="Summary statistics"
    )


class SalaryBreakdownResponse(BaseCurrencyResponse):
    """Response model for salary breakdown analysis with occurrence intelligence."""

    salary_amount: CurrencyAmounts = Field(
        ..., description="Amount per salary payment by currency, when known"
    )
    period_start: str = Field(..., description="Analysis period start date (ISO)")
    period_end: str = Field(..., description="Analysis period end date (ISO)")
    next_salary_date: str = Field(..., description="Next salary date (ISO)")

    # Enhanced breakdown with occurrence awareness
    total_commitments_in_period: CurrencyAmounts = Field(
        ..., description="Total commitment amount in period by currency"
    )
    finite_commitments: list[CommitmentBreakdown] = Field(
        default_factory=list, description="Commitments that will end eventually"
    )
    infinite_commitments: list[CommitmentBreakdown] = Field(
        default_factory=list, description="Ongoing indefinite commitments"
    )
    ending_soon_commitments: list[CommitmentBreakdown] = Field(
        default_factory=list, description="Commitments with < 3 payments remaining"
    )

    # Financial analysis
    remaining_after_commitments: CurrencyAmounts = Field(
        ..., description="Amount remaining after commitments by currency"
    )
    coverage_analysis: str = Field(
        ...,
        description="sufficient/tight/insufficient; unknown when no income "
        "was found; incomplete when a currency has no exchange rate",
    )
    commitment_end_analysis: str = Field(
        ..., description="Analysis of when commitments will end"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Financial planning recommendations"
    )

    # Multi-currency income and conversion
    income_in_period: CurrencyAmounts = Field(
        default_factory=CurrencyAmounts,
        description="All income received in the period, by native currency",
    )
    income_sources: list[IncomeSource] = Field(
        default_factory=list, description="Income streams counted in the period"
    )
    commitments_by_kind: dict[str, CurrencyAmounts] = Field(
        default_factory=dict,
        description="Commitments in the period split into expense, debt_payment "
        "and savings, by currency",
    )
    transfers_in_period: dict[str, CurrencyAmounts] = Field(
        default_factory=dict,
        description="Every scheduled transfer in the period by kind, classified "
        "from the MoneyWiz account types: debt_payment and savings count as "
        "commitments; card_payment (pays expenses already recorded on the card), "
        "internal, non_cash and unclassified do not",
    )
    unclassified_transfers: list[str] = Field(
        default_factory=list,
        description="Transfers whose account types fit no rule; check those "
        "account types in MoneyWiz",
    )
    display_currency: str | None = Field(
        None, description="Currency the combined totals are expressed in"
    )
    totals_in_display_currency: DisplayCurrencyTotals | None = Field(
        None, description="Income, commitments and remaining converted to one currency"
    )
    exchange_rates_used: list[ExchangeRateUsed] = Field(
        default_factory=list, description="Rates used for the combined totals"
    )
    currencies_without_rate: list[str] = Field(
        default_factory=list,
        description="Currencies left out of the combined totals for lack of a rate",
    )


class CommitmentTimelineResponse(BaseModel):
    """Response model for commitment ending timeline."""

    timeline_period: str = Field(..., description="Timeline period analyzed")
    ending_commitments: list[dict[str, Any]] = Field(
        default_factory=list, description="Commitments ending in period"
    )
    cash_flow_changes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Monthly cash flow changes as commitments end",
    )
    total_monthly_relief: CurrencyAmounts = Field(
        ..., description="Total monthly amount freed up by currency"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Strategic recommendations"
    )


class ScheduledTransactionFilters(BaseModel):
    """Model for scheduled transaction filtering options."""

    time_period: str | None = Field(None, description="Time period filter")
    account_ids: list[str] | None = Field(None, description="Account ID filters")
    categories: list[str] | None = Field(None, description="Category filters")
    transaction_types: list[str] | None = Field(
        None, description="Transaction type filters"
    )
    commitment_types: list[str] | None = Field(
        None, description="Commitment type filters (finite/infinite/ending_soon)"
    )
    urgency_levels: list[str] | None = Field(None, description="Urgency level filters")
    include_inactive: bool = Field(
        default=False, description="Include inactive schedules"
    )
    ending_within_days: int | None = Field(
        None, description="Filter by schedules ending within N days"
    )
