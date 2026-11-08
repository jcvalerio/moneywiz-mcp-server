"""Monthly cash view (#66): acceptance cases and card statement logic."""

from datetime import datetime
from decimal import Decimal
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.cash_flow import CashFlowResponse
from moneywiz_mcp_server.models.scheduled_transaction import (
    RecurrenceEndCondition,
    RecurrencePattern,
    ScheduledTransactionModel,
    TransactionType,
)
from moneywiz_mcp_server.services.account_kinds import AccountKind
from moneywiz_mcp_server.services.cash_flow_service import (
    Card,
    CashFlowService,
    closing_date,
    last_closing_before,
)
from moneywiz_mcp_server.services.exchange_rate_service import (
    SOURCE_MONEYWIZ,
    ExchangeRates,
    ExchangeRateService,
    RateInfo,
)
from moneywiz_mcp_server.utils.core_data_time import datetime_to_core_data_timestamp

NOW = datetime(2026, 11, 7, 12)
NOV, DEC, JAN = 0, 1, 2
M, W = RecurrencePattern.MONTHLY, RecurrencePattern.WEEKLY
RATES = ExchangeRates(
    anchor="USD",
    rates={
        "USD": RateInfo(Decimal(1), NOW, SOURCE_MONEYWIZ),
        "CRC": RateInfo(Decimal(500), NOW, SOURCE_MONEYWIZ),
    },
)
KINDS = {
    "bank": AccountKind.LIQUID,
    "card": AccountKind.CREDIT_CARD,
    "payable": AccountKind.CREDIT_CARD,
    "mortgage": AccountKind.LOAN,
    "pension": AccountKind.INVESTMENT,
}


def schedule(
    description,
    amount,
    kind,
    first,
    *,
    source="bank",
    destination=None,
    currency="USD",
    pattern=M,
    interval=1,
    one_time=False,
):
    return ScheduledTransactionModel(
        id=description,
        description=description,
        amount=Decimal(amount),
        currency=currency,
        account_id=source,
        recipient_account_id=destination,
        category="c",
        payee="p",
        transaction_type=kind,
        recurrence_pattern=pattern,
        recurrence_interval=interval,
        next_execution_date=first,
        end_condition=RecurrenceEndCondition.NEVER,
        created_date=NOW,
        entity_type=0,
        database_id=0,
        is_one_time=one_time,
        remaining_occurrences=1 if one_time else None,
    )


def income(amount, first, **kw):
    return schedule("Salary", amount, TransactionType.DEPOSIT, first, **kw)


def bill(description, amount, first, **kw):
    return schedule(description, amount, TransactionType.WITHDRAW, first, **kw)


def transfer(description, amount, first, **kw):
    return schedule(description, amount, TransactionType.TRANSFER_OUT, first, **kw)


def card(history=(), closing_day=18, assumed=False, currency="USD"):
    return Card(
        id="card",
        name="Visa",
        currency=currency,
        closing_day=closing_day,
        closing_day_assumed=assumed,
        history=list(history),
    )


@pytest.fixture
def run(monkeypatch):
    async def _run(
        schedules,
        cards=None,
        budgets=None,
        balance=None,
        months=3,
        **kwargs,
    ):
        service = CashFlowService(MagicMock(spec=DatabaseManager))
        service.scheduled.get_scheduled_transactions = AsyncMock(return_value=schedules)
        service.scheduled.get_account_kinds = AsyncMock(return_value=KINDS)
        service._get_accounts = AsyncMock(return_value={})
        service._get_paid_cards = AsyncMock(
            return_value={c.id: c for c in (cards or [])}
        )
        service._budgets = AsyncMock(
            return_value=budgets or [{} for _ in range(months)]
        )
        service._starting_balance = AsyncMock(return_value=balance or {})
        monkeypatch.setattr(
            ExchangeRateService, "get_rates", AsyncMock(return_value=RATES)
        )
        result = await service.analyze(months=months, now=NOW, **kwargs)
        CashFlowResponse(**result).model_dump(mode="json")  # must serialize
        return result

    return _run


def usd(bucket):
    return bucket.to_json_dict().get("USD", 0.0)


class TestAcceptance:
    async def test_card_payment_above_income_is_short(self, run):
        """#66 case 1: salary 100, one-time card payment 150 -> -50, short."""
        result = await run(
            [
                income("100", datetime(2026, 11, 20)),
                transfer(
                    "Visa statement",
                    "-150",
                    datetime(2026, 11, 25),
                    destination="card",
                    one_time=True,
                ),
            ],
            cards=[card()],
            months=1,
        )
        nov = result["months"][NOV]
        assert usd(nov.left_after_obligations) == -50
        assert nov.verdict == "short"
        [line] = nov.card_details
        assert (line.status, line.amount_source) == ("confirmed", "one_time_payment")

    async def test_bills_on_a_card_are_not_counted_twice(self, run):
        """#66 case 2: a bill charged to the card is inside the card payment."""
        result = await run(
            [
                income("1000", datetime(2026, 11, 20)),
                bill("Phone", "-40", datetime(2026, 11, 10), source="card"),
                transfer(
                    "Visa statement",
                    "-150",
                    datetime(2026, 11, 25),
                    destination="card",
                    one_time=True,
                ),
            ],
            cards=[card()],
            months=1,
        )
        nov = result["months"][NOV]
        assert usd(nov.obligations) == 150
        assert usd(nov.bank_payments) == 0

    async def test_each_month_gets_its_own_verdict(self, run):
        """#66 case 3: 3 paychecks in one month, 2 in the next."""
        result = await run(
            [
                income("1000", datetime(2026, 12, 4), pattern=W, interval=2),
                bill("Rent", "-2500", datetime(2026, 12, 1)),
            ],
            start_month=datetime(2026, 12, 1),
            months=2,
        )
        dec, jan = result["months"]
        assert (usd(dec.income), dec.verdict) == (2000, "short")  # Dec 4, 18
        assert (usd(jan.income), jan.verdict) == (3000, "covered")  # Jan 1, 15, 29
        assert any("2026-12" in r for r in result["recommendations"])

    async def test_closed_statement_is_pending_reconcile(self, run):
        """#66 case 4: closed cycle, no one-time payment: charges minus payments."""
        history = [
            (datetime(2026, 10, 25), Decimal("-300"), False),
            (datetime(2026, 11, 2), Decimal("-200"), False),
            (datetime(2026, 11, 5), Decimal("100"), True),  # paid since close
            (datetime(2026, 11, 20), Decimal("-999"), False),  # next cycle
        ]
        result = await run(
            [transfer("Visa", "-50", datetime(2026, 11, 28), destination="card")],
            cards=[card(history, closing_day=3)],
            months=1,
        )
        [line] = result["months"][NOV].card_details
        assert line.status == "pending_reconcile"
        assert line.amount_source == "statement"
        assert line.cycle_end == closing_date(2026, 11, 3)
        assert line.amount == Decimal("400")  # 300 + 200 - 100
        assert line.note  # the 50 placeholder doesn't match

    async def test_open_cycle_is_projected(self, run):
        """#66 case 5: charges so far + scheduled card bills until closing."""
        history = [(datetime(2026, 11, 1), Decimal("-120"), False)]
        result = await run(
            [
                bill("Streaming", "-30", datetime(2026, 11, 15), source="card"),
                bill("After close", "-500", datetime(2026, 11, 25), source="card"),
                transfer("Visa", "-100", datetime(2026, 12, 5), destination="card"),
            ],
            cards=[card(history, closing_day=18)],
            start_month=datetime(2026, 12, 1),
            months=1,
        )
        [line] = result["months"][0].card_details
        assert line.status == "projected"
        assert line.statement_amount == Decimal("150")  # 120 + 30
        assert line.amount == Decimal("150")  # above the 100 placeholder
        assert "lower than the charges" in line.note

    async def test_open_cycle_keeps_a_higher_placeholder(self, run):
        result = await run(
            [transfer("Visa", "-400", datetime(2026, 12, 5), destination="card")],
            cards=[card([(datetime(2026, 11, 1), Decimal("-120"), False)])],
            start_month=datetime(2026, 12, 1),
            months=1,
        )
        [line] = result["months"][0].card_details
        assert (line.amount, line.amount_source) == (
            Decimal("400"),
            "scheduled_payment",
        )

    async def test_loan_payment_counts_in_full(self, run):
        """#66 case 6."""
        result = await run(
            [
                transfer(
                    "Mortgage", "-900", datetime(2026, 11, 11), destination="mortgage"
                )
            ],
            months=1,
        )
        assert usd(result["months"][NOV].loan_payments) == 900

    async def test_budgets_are_reported_not_judged(self, run):
        """#66 case 7: budgets don't change the verdict."""
        result = await run(
            [income("1000", datetime(2026, 11, 20)), bill("Rent", "-500", NOW)],
            budgets=[{"USD": Decimal("800")}],
            months=1,
        )
        nov = result["months"][NOV]
        assert nov.verdict == "covered"
        assert nov.totals.left_after_obligations == 500
        assert nov.totals.left_after_budgets == -300

    async def test_currencies_are_kept_and_combined(self, run):
        """#66 case 8."""
        result = await run(
            [
                income("1000", datetime(2026, 11, 20)),
                bill("Rent", "-250000", datetime(2026, 11, 25), currency="CRC"),
            ],
            months=1,
        )
        nov = result["months"][NOV]
        assert nov.obligations.to_json_dict() == {"CRC": 250000.0}
        assert nov.totals.obligations == 500  # 250000 / 500
        assert result["exchange_rates_used"][0].currency == "CRC"

    async def test_default_closing_day_is_reported(self, run):
        """#66 case 9."""
        result = await run(
            [transfer("Visa", "-50", datetime(2026, 11, 28), destination="card")],
            cards=[card(closing_day=31, assumed=True)],
            months=1,
        )
        assert result["cards_with_assumed_closing_day"] == ["Visa"]
        assert any("closing day" in r for r in result["recommendations"])


class TestOtherRules:
    async def test_savings_can_be_left_out(self, run):
        schedules = [
            transfer("Pension", "-200", datetime(2026, 11, 15), destination="pension")
        ]
        counted = await run(schedules, months=1)
        skipped = await run(schedules, months=1, count_savings_as_obligations=False)
        assert usd(counted["months"][NOV].savings) == 200
        assert usd(skipped["months"][NOV].savings) == 0

    async def test_bank_balance_is_carried_month_to_month(self, run):
        result = await run(
            [income("1000", datetime(2026, 11, 20)), bill("Rent", "-1500", NOW)],
            balance={"USD": Decimal("2000")},
            months=2,
        )
        nov, dec = result["months"]
        assert nov.verdict == "short"
        assert nov.totals.bank_balance_at_end == 1500
        assert dec.totals.bank_balance_at_end == 1000
        assert any("covers it" in r for r in result["recommendations"])

    async def test_card_without_scheduled_payment_is_paid_the_next_month(self, run):
        history = [(datetime(2026, 10, 10), Decimal("-75"), False)]
        result = await run([], cards=[card(history, closing_day=31)], months=1)
        [line] = result["months"][NOV].card_details
        assert line.payment_date_known is False
        assert line.cycle_end == closing_date(2026, 10, 31)
        assert line.amount == Decimal("75")

    async def test_deposit_into_a_non_bank_account_is_not_income(self, run):
        result = await run(
            [income("500", datetime(2026, 11, 20), source="pension")], months=1
        )
        assert usd(result["months"][NOV].income) == 0
        assert result["months"][NOV].verdict == "no_activity"

    def test_closing_dates_clamp_to_month_end(self):
        assert closing_date(2027, 2, 31) == datetime(2027, 2, 28, 23, 59, 59)
        assert last_closing_before(datetime(2026, 11, 10), 16) == closing_date(
            2026, 10, 16
        )
        assert last_closing_before(datetime(2026, 11, 20), 16) == closing_date(
            2026, 11, 16
        )

    async def test_months_out_of_range(self, run):
        with pytest.raises(ValueError, match="months"):
            await run([], months=13)


class TestPaidCardsAgainstSqlite:
    async def test_only_cards_paid_from_a_bank_are_modelled(self, tmp_path):
        """A payable (card type, settled from a card) is not a card to pay."""
        path = tmp_path / "moneywiz.sqlite"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER, Z_NAME VARCHAR)")
        conn.executemany(
            "INSERT INTO Z_PRIMARYKEY VALUES (?, ?)",
            [
                (10, "BankChequeAccount"),
                (13, "CreditCardAccount"),
                (40, "WithdrawTransaction"),
                (41, "TransferDepositTransaction"),
                (42, "TransferWithdrawTransaction"),
            ],
        )
        conn.execute(
            """CREATE TABLE ZSYNCOBJECT (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER,
               ZNAME TEXT, ZCURRENCYNAME TEXT, ZARCHIVED INTEGER,
               ZSTATEMENTENDDAY INTEGER, ZOPENINGBALANCE REAL, ZACCOUNT2 INTEGER,
               ZAMOUNT1 REAL, ZDATE1 REAL, ZSENDERACCOUNT INTEGER)"""
        )
        ts = datetime_to_core_data_timestamp
        conn.executemany(
            "INSERT INTO ZSYNCOBJECT VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (1, 10, "Bank", "USD", 0, None, 0, None, None, None, None),
                (2, 13, "Visa", "USD", 0, 18, 0, None, None, None, None),
                (3, 13, "Payable", "USD", 0, 31, 0, None, None, None, None),
                # Visa: a purchase and a payment from the bank.
                (100, 40, None, None, None, None, None, 2, -80.0, ts(NOW), None),
                (101, 41, None, None, None, None, None, 2, 50.0, ts(NOW), 1),
                # Payable: receives an installment from the card, never the bank.
                (102, 41, None, None, None, None, None, 3, 30.0, ts(NOW), 2),
                (103, 42, None, None, None, None, None, 2, -30.0, ts(NOW), None),
            ],
        )
        conn.commit()
        conn.close()

        db = DatabaseManager(str(path), read_only=True)
        await db.initialize()
        try:
            service = CashFlowService(db)
            accounts = await service._get_accounts()
            kinds = await service.scheduled.get_account_kinds()
            cards = await service._get_paid_cards(accounts, kinds, [], NOW)
        finally:
            await db.close()

        assert list(cards) == ["2"]
        visa = cards["2"]
        assert (visa.closing_day, visa.closing_day_assumed) == (18, False)
        assert sorted((a, p) for _, a, p in visa.history) == [
            (Decimal("-80.0"), False),
            (Decimal("-30.0"), False),
            (Decimal("50.0"), True),
        ]
