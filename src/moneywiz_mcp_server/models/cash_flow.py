"""Response models for the monthly cash view (#66)."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer

from .base import ApiDateTime
from .currency_types import CurrencyAmounts
from .scheduled_transaction import ExchangeRateUsed


class CashFlowItem(BaseModel):
    """One scheduled movement of money out of (or into) a bank account."""

    description: str = Field(..., description="Schedule description")
    kind: str = Field(
        ...,
        description="income, bank_payment, loan_payment or savings",
    )
    currency: str = Field(..., description="Currency code")
    amount: Decimal = Field(..., description="Amount (positive)")
    date: ApiDateTime = Field(..., description="Scheduled date")

    @field_serializer("amount")
    def _serialize_amount(self, value: Decimal) -> float:
        return float(value)


class CardPaymentLine(BaseModel):
    """What one credit card account needs from the bank in a month."""

    card: str = Field(..., description="Card account name")
    currency: str = Field(..., description="Card account currency")
    amount: Decimal = Field(..., description="Amount counted in this month")
    status: str = Field(
        ...,
        description="confirmed: a one-time payment scheduled after the statement "
        "closed; pending_reconcile: the statement closed but no one-time payment "
        "exists yet; projected: the statement is still open",
    )
    amount_source: str = Field(
        ...,
        description="one_time_payment, scheduled_payment (recurring schedule) or "
        "statement (charges on the card)",
    )
    scheduled_amount: Decimal | None = Field(
        None, description="Recurring scheduled payment in this month, if any"
    )
    statement_amount: Decimal = Field(
        ...,
        description="Charges in the statement cycle this payment covers, minus "
        "payments already made since it closed; for an open cycle, charges so "
        "far plus card bills scheduled until it closes",
    )
    cycle_start: ApiDateTime = Field(..., description="Statement cycle start")
    cycle_end: ApiDateTime = Field(..., description="Statement closing date")
    closing_day_assumed: bool = Field(
        ...,
        description="True when the card's closing day is MoneyWiz's default (31), "
        "so month end is assumed",
    )
    payment_date_known: bool = Field(
        ...,
        description="False when no payment was ever scheduled for this card, so "
        "the statement is assumed to be paid the month after it closes",
    )
    note: str | None = Field(None, description="Warning about this card, if any")

    @field_serializer("amount", "scheduled_amount", "statement_amount")
    def _serialize_amount(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


class CashFlowTotals(BaseModel):
    """A month's figures combined in one display currency."""

    currency: str = Field(..., description="Display currency")
    income: float
    obligations: float
    left_after_obligations: float
    budgets_remaining: float
    left_after_budgets: float
    bank_balance_at_end: float | None = Field(
        None,
        description="Current bank, savings and cash balance plus every month's "
        "left_after_obligations up to this one: the projected bank balance at "
        "month end. Not part of the verdict",
    )


class CashFlowMonth(BaseModel):
    """Income against the money that has to leave bank accounts in a month."""

    month: str = Field(..., description="Calendar month, YYYY-MM")
    period_start: ApiDateTime = Field(..., description="Start of the month")
    period_end: ApiDateTime = Field(..., description="Start of the next month")
    income: CurrencyAmounts = Field(
        ..., description="Scheduled deposits into bank, savings or cash accounts"
    )
    bank_payments: CurrencyAmounts = Field(
        ..., description="Scheduled withdrawals from bank, savings or cash accounts"
    )
    loan_payments: CurrencyAmounts = Field(
        ..., description="Scheduled transfers from a bank account to a Loan"
    )
    savings: CurrencyAmounts = Field(
        ...,
        description="Scheduled transfers from a bank account to an Investment "
        "account (zero when count_savings_as_obligations is false)",
    )
    card_payments: CurrencyAmounts = Field(
        ..., description="What the credit cards need from the bank, see card_details"
    )
    obligations: CurrencyAmounts = Field(
        ..., description="bank_payments + loan_payments + savings + card_payments"
    )
    left_after_obligations: CurrencyAmounts = Field(
        ..., description="income - obligations, by currency"
    )
    budgets_remaining: CurrencyAmounts = Field(
        ...,
        description="Monthly budgets not yet spent (this month) or in full (later "
        "months). Not part of the verdict",
    )
    left_after_budgets: CurrencyAmounts = Field(
        ..., description="left_after_obligations - budgets_remaining"
    )
    totals: CashFlowTotals | None = Field(
        None, description="The figures combined in the display currency"
    )
    verdict: str = Field(
        ...,
        description="covered (10% or more of income left), tight (0-10% left), "
        "short (obligations exceed income), incomplete (a currency has no "
        "exchange rate) or no_activity",
    )
    items: list[CashFlowItem] = Field(
        default_factory=list, description="Scheduled income and non-card obligations"
    )
    card_details: list[CardPaymentLine] = Field(
        default_factory=list, description="One line per card paid this month"
    )


class CashFlowResponse(BaseModel):
    """Monthly cash view: does income cover what has to leave the bank?"""

    display_currency: str | None = Field(
        None, description="Currency the combined totals are expressed in"
    )
    months: list[CashFlowMonth] = Field(..., description="One entry per month")
    starting_balance: CurrencyAmounts = Field(
        ...,
        description="Current balance of bank, savings and cash accounts. Shown "
        "for context, not part of the verdict",
    )
    exchange_rates_used: list[ExchangeRateUsed] = Field(default_factory=list)
    currencies_without_rate: list[str] = Field(default_factory=list)
    cards_with_assumed_closing_day: list[str] = Field(
        default_factory=list,
        description="Cards whose statement closing day is MoneyWiz's default (31); "
        "set the real day in MoneyWiz for accurate statements",
    )
    unclassified_transfers: list[str] = Field(
        default_factory=list,
        description="Transfers whose account types fit no rule; left out",
    )
    recommendations: list[str] = Field(default_factory=list)
