"""Monthly cash view: does income cover the money that leaves bank accounts?

For each calendar month in the horizon, per currency:

    scheduled income into bank/savings/cash accounts
  - scheduled withdrawals from bank/savings/cash accounts
  - bank -> Loan transfers
  - bank -> Investment transfers (count_savings_as_obligations)
  - what each credit card needs from the bank
  = left after obligations -> verdict
  - monthly budgets still to spend (shown, not part of the verdict)

Everything is classified from MoneyWiz account types (services/account_kinds),
never from names. Bills charged to a card are not counted on their own: they
are part of that card's payment.

Card payments. A recurring scheduled card payment repeats one amount, and
MoneyWiz records no edit date on schedules, so the amount can't be trusted as
a statement. The view uses, per card and month:

- a one-time bank -> card payment in the month: confirmed;
- otherwise the statement the payment covers: charges on the card in that
  cycle minus payments already made since it closed (pending_reconcile), or,
  for a cycle still open, charges so far plus card bills scheduled until it
  closes (projected). A recurring scheduled payment counts when it is higher.

The cycle a payment covers is the one closing before the payment date. The
payment date comes from the card's scheduled payments; with none, the
statement is assumed to be paid the month after it closes. The closing day is
the card's ZSTATEMENTENDDAY; MoneyWiz's default 31 is reported as assumed.
"""

import calendar
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import logging
from typing import Any

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.cash_flow import (
    CardPaymentLine,
    CashFlowItem,
    CashFlowMonth,
    CashFlowTotals,
)
from moneywiz_mcp_server.models.currency_types import CurrencyAmounts
from moneywiz_mcp_server.models.scheduled_transaction import (
    ExchangeRateUsed,
    ScheduledTransactionModel,
)
from moneywiz_mcp_server.models.transaction import TransactionType
from moneywiz_mcp_server.services.account_kinds import AccountKind, TransferKind
from moneywiz_mcp_server.services.budget_service import BudgetService
from moneywiz_mcp_server.services.exchange_rate_service import (
    ExchangeRates,
    ExchangeRateService,
)
from moneywiz_mcp_server.services.scheduled_transaction_service import (
    ScheduledTransactionService,
)
from moneywiz_mcp_server.services.transaction_service import ACCOUNT_ENTITY_NAMES
from moneywiz_mcp_server.utils.core_data_time import (
    core_data_timestamp_to_datetime,
    datetime_to_core_data_timestamp,
)
from moneywiz_mcp_server.utils.recurrence import add_months, occurrences_between

logger = logging.getLogger(__name__)

DEFAULT_CLOSING_DAY = 31
# A card counts as one paid from the bank if it received a bank payment
# in this many months, or has a scheduled one.
PAYMENT_HISTORY_MONTHS = 6
# Card transactions that change what the card owes. Incoming transfers are
# handled separately: from a bank they are payments, otherwise they reduce
# the charges.
CHARGE_ENTITY_NAMES = (
    "WithdrawTransaction",
    "DepositTransaction",
    "RefundTransaction",
    "TransferWithdrawTransaction",
)
TRANSFER_IN_ENTITY_NAME = "TransferDepositTransaction"
ZERO = Decimal("0")


def _add(bucket: dict[str, Decimal], currency: str, amount: Decimal) -> None:
    bucket[currency] = bucket.get(currency, ZERO) + amount


def closing_date(year: int, month: int, day: int) -> datetime:
    """End of the statement closing day in a month (clamped to month end)."""
    last = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(day, last), 23, 59, 59)


def last_closing_before(moment: datetime, day: int) -> datetime:
    """The latest closing date strictly before moment."""
    candidate = closing_date(moment.year, moment.month, day)
    if candidate < moment:
        return candidate
    previous = add_months(datetime(moment.year, moment.month, 1), -1)
    return closing_date(previous.year, previous.month, day)


def previous_closing(close: datetime, day: int) -> datetime:
    previous = add_months(datetime(close.year, close.month, 1), -1)
    return closing_date(previous.year, previous.month, day)


@dataclass
class Card:
    """A credit card account paid from the bank."""

    id: str
    name: str
    currency: str
    closing_day: int
    closing_day_assumed: bool
    # Card history used for statements: (date, amount, is_bank_payment).
    history: list[tuple[datetime, Decimal, bool]] = field(default_factory=list)
    # Scheduled charges on the card: (date, amount owed, positive).
    scheduled_charges: list[tuple[datetime, Decimal]] = field(default_factory=list)
    # Scheduled bank -> card payments: (date, amount, one_time).
    scheduled_payments: list[tuple[datetime, Decimal, bool]] = field(
        default_factory=list
    )

    def charges(self, start: datetime, end: datetime, now: datetime) -> Decimal:
        """What the card owes for the cycle (start, end]: recorded charges up to
        now, plus scheduled charges in the cycle. A scheduled date before now
        is an overdue charge that hasn't run (a run schedule moves on to its
        next date), so it isn't in the history yet and still counts."""
        owed = ZERO
        for when, amount, is_payment in self.history:
            if start < when <= min(end, now) and not is_payment:
                owed -= amount  # charges are negative amounts
        for when, amount in self.scheduled_charges:
            if start < when <= end:
                owed += amount
        return owed

    def paid_since(self, start: datetime, now: datetime) -> Decimal:
        return sum(
            (
                amount
                for when, amount, is_payment in self.history
                if is_payment and start < when <= now
            ),
            ZERO,
        )

    @property
    def usual_payment_day(self) -> int | None:
        """Day of month of the card's scheduled payments, if any."""
        if not self.scheduled_payments:
            return None
        return min(self.scheduled_payments)[0].day


@dataclass
class _MonthData:
    items: list[CashFlowItem] = field(default_factory=list)
    cards: list[CardPaymentLine] = field(default_factory=list)


class CashFlowService:
    """Builds the monthly cash view from MoneyWiz schedules and accounts."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.scheduled = ScheduledTransactionService(db_manager)

    async def analyze(
        self,
        months: int = 3,
        start_month: datetime | None = None,
        display_currency: str | None = None,
        exchange_rates: dict[str, float] | None = None,
        count_savings_as_obligations: bool = True,
        include_budgets: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Monthly cash view for `months` calendar months.

        The first month is start_month (default: the current month). For the
        current month this is what is still to come: a schedule that already
        ran this month has moved to its next date, so a date earlier this
        month means it is overdue and still counts. Card statements subtract
        payments already made.
        """
        if not 1 <= months <= 12:
            raise ValueError("months must be between 1 and 12")
        now = now or datetime.now()
        first = start_month or now
        first = datetime(first.year, first.month, 1)
        windows = [
            (add_months(first, i), add_months(first, i + 1)) for i in range(months)
        ]

        schedules = await self.scheduled.get_scheduled_transactions()
        kinds = await self.scheduled.get_account_kinds()
        accounts = await self._get_accounts()
        rates = await ExchangeRateService(self.db_manager).get_rates()

        month_data = [_MonthData() for _ in windows]
        unclassified: list[str] = []
        horizon_start, horizon_end = windows[0][0], windows[-1][1]

        cards = await self._get_paid_cards(accounts, kinds, schedules, now)

        # Card bills from the current month on feed statements that may be
        # paid in the first month shown, even when it starts later.
        occurrences_start = min(horizon_start, datetime(now.year, now.month, 1))
        for t in schedules:
            dates = occurrences_between(
                t.next_execution_date,
                t.recurrence_pattern,
                t.recurrence_interval,
                occurrences_start,
                horizon_end,
                max_occurrences=t.remaining_occurrences,
            )
            if not dates:
                continue
            amount = abs(t.amount)
            source_kind = kinds.get(t.account_id)

            if t.transaction_type == TransactionType.DEPOSIT:
                if source_kind is AccountKind.LIQUID:
                    self._place(month_data, windows, dates, t, "income", amount)
                continue
            if t.transaction_type == TransactionType.WITHDRAW:
                if source_kind is AccountKind.LIQUID:
                    self._place(month_data, windows, dates, t, "bank_payment", amount)
                elif t.account_id in cards:
                    cards[t.account_id].scheduled_charges.extend(
                        (d, amount) for d in dates
                    )
                continue

            kind = ScheduledTransactionService.transfer_kind(t, kinds)
            if kind is TransferKind.DEBT_PAYMENT:
                self._place(month_data, windows, dates, t, "loan_payment", amount)
            elif kind is TransferKind.SAVINGS:
                if count_savings_as_obligations:
                    self._place(month_data, windows, dates, t, "savings", amount)
            elif kind is TransferKind.CARD_PAYMENT:
                card = cards.get(t.recipient_account_id or "")
                if card:
                    card.scheduled_payments.extend(
                        (d, amount, t.is_one_time) for d in dates
                    )
            elif kind is TransferKind.NON_CASH and t.account_id in cards:
                # e.g. an installment moved from the card to a payable: the
                # card owes it on its statement.
                cards[t.account_id].scheduled_charges.extend((d, amount) for d in dates)
            elif kind is TransferKind.UNCLASSIFIED:
                unclassified.append(t.description)

        for card in cards.values():
            for i, (start, end) in enumerate(windows):
                line = self._card_line(card, start, end, now)
                if line is not None:
                    month_data[i].cards.append(line)

        budgets = await self._budgets(windows, now) if include_budgets else None
        display = (display_currency or "").upper() or rates.anchor
        display_rates = (
            rates.rebase(display).with_overrides(exchange_rates) if display else None
        )

        starting = await self._starting_balance()
        balance: Decimal | None = None
        # Today's balance is only a valid opening balance for the current month.
        starts_now = windows[0][0] == datetime(now.year, now.month, 1)
        if display_rates is not None and starts_now:
            converted = [display_rates.convert(a, c) for c, a in starting.items()]
            if all(v is not None for v in converted):
                balance = sum((v for v in converted if v is not None), ZERO)

        months_out: list[CashFlowMonth] = []
        without_rate: set[str] = set()
        for i, (start, end) in enumerate(windows):
            budget = budgets[i] if budgets else {}
            month, missing = self._build_month(
                month_data[i], start, end, budget, display, display_rates
            )
            if month.totals is not None and balance is not None and not missing:
                balance += Decimal(str(month.totals.left_after_obligations))
                month.totals.bank_balance_at_end = round(float(balance), 2)
            else:
                balance = None
            without_rate |= missing
            months_out.append(month)

        rates_used = self._rates_used(display, display_rates, months_out)
        assumed = sorted(c.name for c in cards.values() if c.closing_day_assumed)
        return {
            "display_currency": display,
            "months": months_out,
            "starting_balance": CurrencyAmounts(starting),
            "exchange_rates_used": rates_used,
            "currencies_without_rate": sorted(without_rate),
            "cards_with_assumed_closing_day": assumed,
            "unclassified_transfers": sorted(set(unclassified)),
            "recommendations": self._recommendations(
                months_out,
                assumed,
                sorted(without_rate),
                unclassified,
                budgets_failed=include_budgets and budgets is None,
                balance_shown=starts_now,
            ),
        }

    # --- Inputs --------------------------------------------------------

    async def _get_accounts(self) -> dict[str, dict[str, Any]]:
        entity_map = await self.db_manager.get_entity_name_map()
        ids = [entity_map[n] for n in ACCOUNT_ENTITY_NAMES if n in entity_map]
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        rows = await self.db_manager.execute_query(
            "SELECT Z_PK, Z_ENT, ZNAME, ZCURRENCYNAME, ZARCHIVED, ZSTATEMENTENDDAY, "  # nosec B608 - placeholders only
            f"ZOPENINGBALANCE FROM ZSYNCOBJECT WHERE Z_ENT IN ({placeholders})",
            tuple(ids),
        )
        return {str(r["Z_PK"]): r for r in rows}

    async def _get_paid_cards(
        self,
        accounts: dict[str, dict[str, Any]],
        kinds: dict[str, AccountKind],
        schedules: list[ScheduledTransactionModel],
        now: datetime,
    ) -> dict[str, Card]:
        """Credit card accounts paid from bank accounts, with their history.

        A card qualifies if it has a scheduled bank -> card payment or received
        a payment from a bank account recently. Credit-card-type accounts used
        for other purposes (e.g. payables settled from a card) don't.
        """
        card_ids = {
            pk
            for pk, row in accounts.items()
            if kinds.get(pk) is AccountKind.CREDIT_CARD and not row.get("ZARCHIVED")
        }
        if not card_ids:
            return {}
        liquid = {pk for pk, k in kinds.items() if k is AccountKind.LIQUID}
        paid = {
            t.recipient_account_id
            for t in schedules
            if t.recipient_account_id in card_ids and t.account_id in liquid
        }

        entity_map = await self.db_manager.get_entity_name_map()
        charge_ents = [entity_map[n] for n in CHARGE_ENTITY_NAMES if n in entity_map]
        transfer_in = entity_map.get(TRANSFER_IN_ENTITY_NAME)
        since = add_months(datetime(now.year, now.month, 1), -PAYMENT_HISTORY_MONTHS)
        card_list = sorted(card_ids)
        rows: list[dict[str, Any]] = []
        if charge_ents and transfer_in is not None:
            ents = [*charge_ents, transfer_in]
            rows = await self.db_manager.execute_query(
                "SELECT ZACCOUNT2 AS account, Z_ENT AS ent, ZAMOUNT1 AS amount, "  # nosec B608 - placeholders only
                "ZDATE1 AS date, ZSENDERACCOUNT AS sender FROM ZSYNCOBJECT "
                f"WHERE Z_ENT IN ({','.join('?' for _ in ents)}) "
                f"AND ZACCOUNT2 IN ({','.join('?' for _ in card_list)}) "
                "AND ZDATE1 >= ? AND ZAMOUNT1 IS NOT NULL",
                (
                    *ents,
                    *(int(c) for c in card_list),
                    datetime_to_core_data_timestamp(since),
                ),
            )

        history: dict[str, list[tuple[datetime, Decimal, bool]]] = {}
        for row in rows:
            account = str(row["account"])
            is_payment = row["ent"] == transfer_in and str(row["sender"]) in liquid
            if is_payment:
                paid.add(account)
            history.setdefault(account, []).append(
                (
                    core_data_timestamp_to_datetime(row["date"]),
                    Decimal(str(row["amount"])),
                    is_payment,
                )
            )

        cards: dict[str, Card] = {}
        for pk in paid:
            if pk is None:
                continue
            row = accounts[pk]
            day = row.get("ZSTATEMENTENDDAY")
            assumed = not isinstance(day, int) or day in (0, DEFAULT_CLOSING_DAY)
            cards[pk] = Card(
                id=pk,
                name=row.get("ZNAME") or f"Account {pk}",
                currency=row.get("ZCURRENCYNAME") or "USD",
                closing_day=DEFAULT_CLOSING_DAY if assumed else int(day),
                closing_day_assumed=assumed,
                history=history.get(pk, []),
            )
        return cards

    async def _budgets(
        self, windows: list[tuple[datetime, datetime]], now: datetime
    ) -> list[dict[str, Decimal]] | None:
        """Monthly budgets per month: unspent this month, in full later."""
        try:
            budgets = await BudgetService(self.db_manager).get_budgets()
        except Exception as e:
            logger.warning(f"Could not read budgets: {e}")
            return None
        current = datetime(now.year, now.month, 1)
        out: list[dict[str, Decimal]] = []
        for start, _end in windows:
            bucket: dict[str, Decimal] = {}
            for b in budgets:
                if not b.is_active or b.period.value != "monthly":
                    continue
                if start < current:
                    continue
                amount = (
                    max(b.remaining_amount, ZERO)
                    if start == current
                    else b.budget_amount
                )
                _add(bucket, b.currency, amount)
            out.append(bucket)
        return out

    async def _starting_balance(self) -> dict[str, Decimal]:
        from moneywiz_mcp_server.services.account_service import AccountService

        balances: dict[str, Decimal] = {}
        for account in await AccountService(self.db_manager).list_accounts():
            if account["type"] in ("checking", "savings", "cash"):
                _add(
                    balances,
                    account["currency"],
                    Decimal(str(account["balance"] or 0)),
                )
        return balances

    # --- Placement -----------------------------------------------------

    @staticmethod
    def _place(
        month_data: list[_MonthData],
        windows: list[tuple[datetime, datetime]],
        dates: list[datetime],
        t: ScheduledTransactionModel,
        kind: str,
        amount: Decimal,
    ) -> None:
        for d in dates:
            for i, (start, end) in enumerate(windows):
                if start <= d < end:
                    month_data[i].items.append(
                        CashFlowItem(
                            description=t.description,
                            kind=kind,
                            currency=t.currency,
                            amount=amount,
                            date=d,
                        )
                    )
                    break

    @staticmethod
    def _card_line(
        card: Card, start: datetime, end: datetime, now: datetime
    ) -> CardPaymentLine | None:
        payments = [p for p in card.scheduled_payments if start <= p[0] < end]
        one_time = sum((a for d, a, once in payments if once), ZERO)
        recurring = sum((a for d, a, once in payments if not once), ZERO)

        payment_date: datetime | None
        if payments:
            payment_date = min(payments)[0]
        elif card.usual_payment_day is not None:
            last = calendar.monthrange(start.year, start.month)[1]
            payment_date = datetime(
                start.year, start.month, min(card.usual_payment_day, last), 12
            )
        else:
            payment_date = None

        if payment_date is not None:
            cycle_end = last_closing_before(payment_date, card.closing_day)
        else:
            previous = add_months(start, -1)
            cycle_end = closing_date(previous.year, previous.month, card.closing_day)
        cycle_start = previous_closing(cycle_end, card.closing_day)

        is_open = cycle_end > now
        statement = card.charges(cycle_start, cycle_end, now)
        if not is_open:
            statement -= card.paid_since(cycle_end, now)
        statement = max(statement, ZERO)

        note = None
        if one_time > 0:
            amount, source, status = one_time, "one_time_payment", "confirmed"
        elif not is_open:
            # The cycle has closed: its charges are known, a placeholder isn't.
            amount, source, status = statement, "statement", "pending_reconcile"
            if recurring > 0 and recurring != statement:
                note = (
                    f"The scheduled payment ({recurring:,.2f}) differs from the "
                    f"closed statement ({statement:,.2f}); the statement is used."
                )
        else:
            # Open cycle: charges so far are a floor; the scheduled amount is
            # the user's plan for the rest of the cycle.
            status = "projected"
            if recurring >= statement and recurring > 0:
                amount, source = recurring, "scheduled_payment"
            else:
                amount, source = statement, "statement"
                if recurring > 0:
                    note = (
                        f"The scheduled payment ({recurring:,.2f}) is lower than "
                        f"the charges so far ({statement:,.2f}); the charges are "
                        "used."
                    )
        if amount <= 0:
            return None
        return CardPaymentLine(
            card=card.name,
            currency=card.currency,
            amount=amount,
            status=status,
            amount_source=source,
            scheduled_amount=recurring if recurring > 0 else None,
            statement_amount=statement,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            closing_day_assumed=card.closing_day_assumed,
            payment_date_known=payment_date is not None,
            note=note,
        )

    # --- Output --------------------------------------------------------

    def _build_month(
        self,
        data: _MonthData,
        start: datetime,
        end: datetime,
        budgets: dict[str, Decimal],
        display: str | None,
        display_rates: ExchangeRates | None,
    ) -> tuple[CashFlowMonth, set[str]]:
        lines: dict[str, dict[str, Decimal]] = {
            k: {} for k in ("income", "bank_payment", "loan_payment", "savings")
        }
        for item in data.items:
            _add(lines[item.kind], item.currency, item.amount)
        cards: dict[str, Decimal] = {}
        for card in data.cards:
            _add(cards, card.currency, card.amount)

        obligations: dict[str, Decimal] = {}
        for bucket in (
            lines["bank_payment"],
            lines["loan_payment"],
            lines["savings"],
            cards,
        ):
            for c, a in bucket.items():
                _add(obligations, c, a)
        currencies = sorted(set(lines["income"]) | set(obligations) | set(budgets))
        left = {
            c: lines["income"].get(c, ZERO) - obligations.get(c, ZERO)
            for c in currencies
        }
        left_after_budgets = {c: left[c] - budgets.get(c, ZERO) for c in currencies}

        totals = None
        missing: set[str] = set()
        if display and display_rates is not None:

            def combined(bucket: dict[str, Decimal]) -> Decimal:
                total = ZERO
                for c, a in bucket.items():
                    converted = display_rates.convert(a, c)
                    if converted is None:
                        missing.add(c)
                    else:
                        total += converted
                return total

            income_total = combined(lines["income"])
            obligations_total = combined(obligations)
            budgets_total = combined(budgets)
            totals = CashFlowTotals(
                currency=display,
                income=round(float(income_total), 2),
                obligations=round(float(obligations_total), 2),
                left_after_obligations=round(
                    float(income_total - obligations_total), 2
                ),
                budgets_remaining=round(float(budgets_total), 2),
                left_after_budgets=round(
                    float(income_total - obligations_total - budgets_total), 2
                ),
                bank_balance_at_end=None,
            )
            verdict = (
                "incomplete"
                if missing
                else self._verdict(income_total, obligations_total)
            )
        else:
            verdict = "incomplete"

        month = CashFlowMonth(
            month=start.strftime("%Y-%m"),
            period_start=start,
            period_end=end,
            income=CurrencyAmounts(lines["income"]),
            bank_payments=CurrencyAmounts(lines["bank_payment"]),
            loan_payments=CurrencyAmounts(lines["loan_payment"]),
            savings=CurrencyAmounts(lines["savings"]),
            card_payments=CurrencyAmounts(cards),
            obligations=CurrencyAmounts(obligations),
            left_after_obligations=CurrencyAmounts(left),
            budgets_remaining=CurrencyAmounts(budgets),
            left_after_budgets=CurrencyAmounts(left_after_budgets),
            totals=totals,
            verdict=verdict,
            items=sorted(data.items, key=lambda x: x.date),
            card_details=sorted(data.cards, key=lambda c: (c.currency, c.card)),
        )
        return month, missing

    @staticmethod
    def _verdict(income: Decimal, obligations: Decimal) -> str:
        if income <= 0 and obligations <= 0:
            return "no_activity"
        left = income - obligations
        if left < 0:
            return "short"
        if left < income * Decimal("0.1"):
            return "tight"
        return "covered"

    @staticmethod
    def _rates_used(
        display: str | None,
        display_rates: ExchangeRates | None,
        months: list[CashFlowMonth],
    ) -> list[ExchangeRateUsed]:
        if not display or display_rates is None:
            return []
        currencies: set[str] = set()
        for m in months:
            for bucket in (m.income, m.obligations, m.budgets_remaining):
                currencies |= set(bucket.to_json_dict())
        out = []
        for c in sorted(currencies - {display}):
            info = display_rates.rates.get(c)
            if info is not None:
                out.append(
                    ExchangeRateUsed(
                        currency=c,
                        units_per_display_currency=float(info.units_per_anchor),
                        as_of=info.as_of,
                        source=info.source,
                    )
                )
        return out

    @staticmethod
    def _recommendations(
        months: list[CashFlowMonth],
        assumed: list[str],
        without_rate: list[str],
        unclassified: list[str],
        budgets_failed: bool = False,
        balance_shown: bool = True,
    ) -> list[str]:
        out: list[str] = []
        if budgets_failed:
            out.append("📌 Budgets couldn't be read, so budgets_remaining is empty.")
        if not balance_shown:
            out.append(
                "📌 bank_balance_at_end is only projected when the first month "
                "is the current one."
            )
        for m in months:
            if m.verdict == "short" and m.totals is not None:
                gap = -m.totals.left_after_obligations
                end_balance = m.totals.bank_balance_at_end
                cover = (
                    f" Your bank balance covers it: about {end_balance:,.2f} "
                    f"{m.totals.currency} left at month end."
                    if end_balance is not None and end_balance >= 0
                    else " Your current bank balance doesn't cover it: paying "
                    "every card in full isn't possible and the rest rolls over "
                    "as card debt."
                    if end_balance is not None
                    else ""
                )
                out.append(
                    f"⚠️ {m.month}: obligations exceed income by {gap:,.2f} "
                    f"{m.totals.currency}.{cover}"
                )
            pending = [
                c.card for c in m.card_details if c.status == "pending_reconcile"
            ]
            if pending:
                out.append(
                    f"📌 {m.month}: statements closed but not reconciled: "
                    f"{', '.join(pending)}. Reconcile them and schedule a "
                    "one-time payment to confirm the amount."
                )
            low = [c.card for c in m.card_details if c.note]
            if low:
                out.append(
                    f"📌 {m.month}: scheduled card payments that don't match the "
                    "statement (see each card's note): "
                    f"{', '.join(low)}."
                )
        if assumed:
            out.append(
                f"📌 {len(assumed)} cards use MoneyWiz's default closing day "
                "(31), so month end is assumed. Set each card's real statement "
                "closing day for accurate statements."
            )
        if without_rate:
            out.append(
                f"📌 No exchange rate for {', '.join(without_rate)}; months "
                "using it have no verdict (incomplete). Pass exchange_rates."
            )
        if unclassified:
            out.append(
                f"📌 Left out, account types fit no rule: "
                f"{', '.join(sorted(set(unclassified)))}."
            )
        return out
