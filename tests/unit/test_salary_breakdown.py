"""Salary breakdown: multi-currency income, paycheck counting, transfers (#64)."""

from datetime import datetime
from decimal import Decimal
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.scheduled_transaction import (
    RecurrenceEndCondition,
    RecurrencePattern,
    SalaryBreakdownResponse,
    ScheduledTransactionModel,
    TransactionType,
)
from moneywiz_mcp_server.services.account_kinds import (
    AccountKind,
    TransferKind,
    classify_transfer,
)
from moneywiz_mcp_server.services.exchange_rate_service import (
    SOURCE_MONEYWIZ,
    ExchangeRates,
    ExchangeRateService,
    RateInfo,
)
from moneywiz_mcp_server.services.scheduled_transaction_service import (
    ScheduledEntityRole,
    ScheduledTransactionService,
)
from moneywiz_mcp_server.utils.core_data_time import datetime_to_core_data_timestamp
from moneywiz_mcp_server.utils.recurrence import parse_frequency

START = datetime(2027, 1, 1, 12)
RATE_DATE = datetime(2026, 12, 30)
USD_BASE = ExchangeRates(
    anchor="USD",
    rates={
        "USD": RateInfo(Decimal(1), RATE_DATE, SOURCE_MONEYWIZ),
        "CRC": RateInfo(Decimal(500), RATE_DATE, SOURCE_MONEYWIZ),
    },
)

W, M = RecurrencePattern.WEEKLY, RecurrencePattern.MONTHLY


def schedule(
    description: str,
    amount: str,
    currency: str,
    kind: TransactionType,
    pattern: RecurrencePattern = M,
    interval: int = 1,
    first: datetime = START,
    source: str = "bank",
    destination: str | None = None,
) -> ScheduledTransactionModel:
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
        created_date=START,
        entity_type=0,
        database_id=0,
    )


def deposit(*args, **kwargs):
    return schedule(*args, kind=TransactionType.DEPOSIT, **kwargs)


def bill(*args, **kwargs):
    return schedule(*args, kind=TransactionType.WITHDRAW, **kwargs)


def transfer(*args, **kwargs):
    return schedule(*args, kind=TransactionType.TRANSFER_OUT, **kwargs)


# Test accounts by MoneyWiz type: ids are what schedules reference.
ACCOUNT_KINDS = {
    "bank": AccountKind.LIQUID,
    "savings": AccountKind.LIQUID,
    "card": AccountKind.CREDIT_CARD,
    "payable": AccountKind.CREDIT_CARD,
    "mortgage": AccountKind.LOAN,
    "pension": AccountKind.INVESTMENT,
}


@pytest.fixture
def make_service(monkeypatch):
    def _make(schedules, rates=USD_BASE):
        service = ScheduledTransactionService(MagicMock(spec=DatabaseManager))
        service.get_scheduled_transactions = AsyncMock(return_value=schedules)
        service.get_account_kinds = AsyncMock(return_value=ACCOUNT_KINDS)
        monkeypatch.setattr(
            ExchangeRateService, "get_rates", AsyncMock(return_value=rates)
        )
        return service

    return _make


async def breakdown(service, **kwargs):
    kwargs.setdefault("next_salary_date", START)
    kwargs.setdefault("planning_horizon_months", 3)
    result = await service.calculate_salary_breakdown(**kwargs)
    SalaryBreakdownResponse(**result).model_dump(mode="json")  # must serialize
    return result


class TestPaychecks:
    async def test_biweekly_scheduled_salary_counts_every_paycheck(self, make_service):
        service = make_service(
            [deposit("Salary", "2000", "USD", pattern=W, interval=2)]
        )
        result = await breakdown(service)
        # Jan 1 + every 14 days, before Apr 1: Jan 1, 15, 29, Feb 12, 26, Mar 12, 26
        assert result["income_sources"][0].payments_in_period == 7
        assert result["income_in_period"]["USD"] == Decimal("14000")
        assert result["salary_amount"]["USD"] == Decimal("2000")

    async def test_monthly_provided_salary_counts_three_payments(self, make_service):
        service = make_service([])
        result = await breakdown(
            service, salary_amount=Decimal("3000"), salary_currency="USD"
        )
        assert result["income_in_period"]["USD"] == Decimal("9000")

    async def test_provided_salary_uses_scheduled_frequency(self, make_service):
        service = make_service(
            [deposit("Salary", "2000", "USD", pattern=W, interval=2)]
        )
        result = await breakdown(service, salary_amount=Decimal("2500"))
        assert result["income_in_period"]["USD"] == Decimal("17500")  # 7 x 2500

    async def test_explicit_frequency_wins(self, make_service):
        service = make_service([])
        result = await breakdown(
            service,
            salary_amount=Decimal("1000"),
            salary_currency="USD",
            salary_frequency="weekly",
        )
        assert result["income_sources"][0].payments_in_period == 13

    async def test_window_is_measured_from_the_salary_date(self, make_service):
        """A salary date far in the future still counts every occurrence."""
        service = make_service(
            [
                deposit("Salary", "1000", "USD", first=START),
                bill("Rent", "-500", "USD", first=START),
            ]
        )
        later = datetime(2028, 1, 1, 12)
        result = await breakdown(
            service, next_salary_date=later, planning_horizon_months=6
        )
        assert result["income_in_period"]["USD"] == Decimal("6000")
        assert result["total_commitments_in_period"]["USD"] == Decimal("3000")


class TestCurrencies:
    async def test_income_in_two_currencies_is_kept_native_and_combined(
        self, make_service
    ):
        service = make_service(
            [
                deposit("Salary", "1000", "USD"),
                deposit("Side income", "100000", "CRC"),
                bill("Rent", "-100000", "CRC"),
            ]
        )
        result = await breakdown(service)
        assert result["income_in_period"]["USD"] == Decimal("3000")
        assert result["income_in_period"]["CRC"] == Decimal("300000")
        # CRC income covers the CRC bill: no phantom CRC deficit.
        assert result["remaining_after_commitments"]["CRC"] == Decimal("0")
        totals = result["totals_in_display_currency"]
        assert totals.currency == "USD"
        assert totals.income == pytest.approx(3600)  # 3000 + 300000 / 500
        assert totals.commitments == pytest.approx(600)
        assert result["coverage_analysis"] == "sufficient"
        [rate] = result["exchange_rates_used"]
        assert (rate.currency, rate.units_per_display_currency) == ("CRC", 500)

    async def test_display_currency_can_be_crc(self, make_service):
        service = make_service(
            [deposit("Salary", "100", "USD"), deposit("x", "500", "CRC")]
        )
        result = await breakdown(
            service, planning_horizon_months=1, display_currency="CRC"
        )
        totals = result["totals_in_display_currency"]
        assert totals.currency == "CRC"
        assert totals.income == pytest.approx(50500)  # 100 USD x 500 + 500 CRC

    async def test_provided_salary_replaces_only_its_currency(self, make_service):
        service = make_service(
            [deposit("Salary", "1000", "USD"), deposit("Side income", "50000", "CRC")]
        )
        result = await breakdown(
            service, salary_amount=Decimal("1200"), salary_currency="USD"
        )
        assert result["income_in_period"]["USD"] == Decimal("3600")
        assert result["income_in_period"]["CRC"] == Decimal("150000")
        replaced = [r for r in result["recommendations"] if "replaces" in r]
        assert len(replaced) == 1
        assert "Salary" in replaced[0]
        assert "Side income" not in replaced[0]

    async def test_caller_rates_override_moneywiz(self, make_service):
        service = make_service([deposit("x", "1000", "CRC")])
        result = await breakdown(
            service, planning_horizon_months=1, exchange_rates={"CRC": 250}
        )
        assert result["totals_in_display_currency"].income == pytest.approx(4)
        assert result["exchange_rates_used"][0].source == "provided"

    async def test_missing_rate_is_reported_not_guessed(self, make_service):
        service = make_service(
            [deposit("Salary", "1000", "USD"), bill("x", "-10", "EUR")]
        )
        result = await breakdown(service, planning_horizon_months=1)
        assert result["currencies_without_rate"] == ["EUR"]
        assert result["totals_in_display_currency"].commitments == 0
        assert any("EUR" in r for r in result["recommendations"])
        # A currency left out of the totals means no verdict.
        assert result["coverage_analysis"] == "incomplete"

    async def test_no_income_is_unknown_not_insufficient(self, make_service):
        service = make_service([bill("Rent", "-500", "USD")])
        result = await breakdown(service)
        assert result["coverage_analysis"] == "unknown"

    async def test_salary_currency_required_when_ambiguous(self, make_service):
        service = make_service(
            [bill("a", "-1", "USD"), bill("b", "-1", "CRC")],
            rates=ExchangeRates(anchor=None),
        )
        with pytest.raises(ValueError, match="salary_currency"):
            await breakdown(service, salary_amount=Decimal("1000"))


class TestTransfers:
    SCHEDULES = (
        deposit("Salary", "1000", "USD"),
        bill("Phone on card", "-400", "USD", source="card"),
        transfer("Card payment", "-900", "USD", destination="card"),
        transfer("Mortgage", "-300", "USD", destination="mortgage"),
        transfer("Pension", "-100", "USD", destination="pension"),
        transfer("Installment", "-50", "USD", source="card", destination="payable"),
        transfer("To savings", "-20", "USD", destination="savings"),
        transfer("Mystery", "-10", "USD", destination="deleted-account"),
    )

    async def test_transfers_are_classified_by_account_type(self, make_service):
        result = await breakdown(
            make_service(list(self.SCHEDULES)), planning_horizon_months=1
        )
        # Bills + loan payment + pension contribution; not the card payment.
        assert result["total_commitments_in_period"]["USD"] == Decimal("800")
        by_kind = result["commitments_by_kind"]
        assert by_kind["expense"]["USD"] == Decimal("400")
        assert by_kind["debt_payment"]["USD"] == Decimal("300")
        assert by_kind["savings"]["USD"] == Decimal("100")
        transfers = {k: v["USD"] for k, v in result["transfers_in_period"].items()}
        assert transfers == {
            "card_payment": Decimal("900"),
            "debt_payment": Decimal("300"),
            "savings": Decimal("100"),
            "non_cash": Decimal("50"),
            "internal": Decimal("20"),
            "unclassified": Decimal("10"),
        }
        assert result["unclassified_transfers"] == ["Mystery"]
        assert any("Mystery" in r for r in result["recommendations"])
        kinds = {c.description: c.kind for c in result["infinite_commitments"]}
        assert kinds == {
            "Phone on card": "expense",
            "Mortgage": "debt_payment",
            "Pension": "savings",
        }

    async def test_savings_can_be_left_out_of_commitments(self, make_service):
        result = await breakdown(
            make_service(list(self.SCHEDULES)),
            planning_horizon_months=1,
            count_savings_as_commitments=False,
        )
        assert result["total_commitments_in_period"]["USD"] == Decimal("700")
        assert "savings" not in result["commitments_by_kind"]
        assert result["transfers_in_period"]["savings"]["USD"] == Decimal("100")

    @pytest.mark.parametrize(
        ("source", "destination", "expected"),
        [
            (AccountKind.LIQUID, AccountKind.LOAN, TransferKind.DEBT_PAYMENT),
            (AccountKind.LIQUID, AccountKind.CREDIT_CARD, TransferKind.CARD_PAYMENT),
            (AccountKind.LIQUID, AccountKind.INVESTMENT, TransferKind.SAVINGS),
            (AccountKind.LIQUID, AccountKind.LIQUID, TransferKind.INTERNAL),
            (AccountKind.INVESTMENT, AccountKind.LIQUID, TransferKind.INTERNAL),
            (AccountKind.INVESTMENT, AccountKind.INVESTMENT, TransferKind.INTERNAL),
            (AccountKind.CREDIT_CARD, AccountKind.LIQUID, TransferKind.NON_CASH),
            (AccountKind.CREDIT_CARD, AccountKind.CREDIT_CARD, TransferKind.NON_CASH),
            (AccountKind.LOAN, AccountKind.LIQUID, TransferKind.NON_CASH),
            (AccountKind.INVESTMENT, AccountKind.LOAN, TransferKind.UNCLASSIFIED),
            (None, AccountKind.LOAN, TransferKind.UNCLASSIFIED),
            (AccountKind.LIQUID, None, TransferKind.UNCLASSIFIED),
        ],
    )
    def test_classification_rules(self, source, destination, expected):
        assert classify_transfer(source, destination) is expected

    def test_incoming_transfer_is_read_in_reverse(self):
        incoming = schedule(
            "Refund to bank",
            "50",
            "USD",
            kind=TransactionType.TRANSFER_IN,
            source="bank",
            destination="mortgage",
        )
        # Money flows mortgage -> bank: out of a loan, so not a payment.
        assert (
            ScheduledTransactionService.transfer_kind(incoming, ACCOUNT_KINDS)
            is TransferKind.NON_CASH
        )

    async def test_account_kinds_come_from_entity_types_against_sqlite(self, tmp_path):
        path = tmp_path / "moneywiz.sqlite"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER, Z_NAME VARCHAR)")
        conn.executemany(
            "INSERT INTO Z_PRIMARYKEY VALUES (?, ?)",
            [(10, "BankChequeAccount"), (16, "LoanAccount"), (99, "Category")],
        )
        conn.execute("CREATE TABLE ZSYNCOBJECT (Z_PK INTEGER PRIMARY KEY, Z_ENT INT)")
        conn.executemany(
            "INSERT INTO ZSYNCOBJECT VALUES (?, ?)", [(1, 10), (2, 16), (3, 99)]
        )
        conn.commit()
        conn.close()

        db = DatabaseManager(str(path), read_only=True)
        await db.initialize()
        try:
            kinds = await ScheduledTransactionService(db).get_account_kinds()
        finally:
            await db.close()
        assert kinds == {"1": AccountKind.LIQUID, "2": AccountKind.LOAN}

    @pytest.mark.parametrize(
        ("amount", "expected"),
        [(-50.0, TransactionType.TRANSFER_OUT), (50.0, TransactionType.TRANSFER_IN)],
    )
    def test_scheduled_transfers_are_typed_as_transfers(self, amount, expected):
        service = ScheduledTransactionService(MagicMock(spec=DatabaseManager))
        assert (
            service._infer_transaction_type(amount, ScheduledEntityRole.TRANSFER)
            == expected
        )


class TestScheduleEnds:
    """One-time schedules and schedules that end are counted only while active."""

    def end_of(self, record, first=START):
        return ScheduledTransactionService._end_of_schedule(record, first, M, 1)

    def test_one_time_schedule_runs_once(self):
        assert self.end_of({"ZISREPEATABLE1": 0}) == (
            True,
            RecurrenceEndCondition.AFTER_OCCURRENCES,
            START,
            1,
        )

    def test_repeating_schedule_without_end_is_infinite(self):
        assert self.end_of({"ZISREPEATABLE1": 1}) == (
            False,
            RecurrenceEndCondition.NEVER,
            None,
            None,
        )

    def test_end_date_counts_remaining_payments(self):
        # Jan 1, Feb 1, Mar 1; the stored end is earlier in the day.
        end = datetime_to_core_data_timestamp(datetime(2027, 3, 1, 8))
        one_time, condition, final, remaining = self.end_of(
            {"ZISREPEATABLE1": 1, "ZLASTEXECUTEDATE": end}
        )
        assert (one_time, condition, remaining) == (
            False,
            RecurrenceEndCondition.ON_DATE,
            3,
        )
        assert final.date() == datetime(2027, 3, 1).date()

    async def test_one_time_schedule_that_already_ran_is_skipped(self):
        service = ScheduledTransactionService(MagicMock(spec=DatabaseManager))
        record = {
            "Z_PK": 1,
            "ZAMOUNT": -10.0,
            "ZEXECUTEDATE": datetime_to_core_data_timestamp(START),
            "ZISREPEATABLE1": 0,
            "ZEXECUTESCOUNT": 1,
        }
        assert (
            await service._convert_record_to_model(
                record, 0, ScheduledEntityRole.REGULAR
            )
            is None
        )

    def test_schedule_past_its_end_has_no_payments_left(self):
        end = datetime_to_core_data_timestamp(datetime(2026, 12, 1))
        assert self.end_of({"ZISREPEATABLE1": 1, "ZLASTEXECUTEDATE": end})[3] == 0

    async def test_breakdown_counts_one_time_once_and_stops_at_the_end(
        self, make_service
    ):
        one_time = bill(
            "Repair", "-150", "USD", first=datetime(2027, 1, 20)
        ).model_copy(update={"is_one_time": True, "remaining_occurrences": 1})
        ending = bill("Last installments", "-100", "USD").model_copy(
            update={
                "end_condition": RecurrenceEndCondition.ON_DATE,
                "remaining_occurrences": 2,
            }
        )
        card_payment = transfer(
            "Statement", "-500", "USD", destination="card"
        ).model_copy(update={"is_one_time": True, "remaining_occurrences": 1})
        result = await breakdown(
            make_service(
                [deposit("Salary", "1000", "USD"), one_time, ending, card_payment]
            )
        )
        # 150 once + 100 twice; the card payment is reported, not counted.
        assert result["total_commitments_in_period"]["USD"] == Decimal("350")
        assert result["transfers_in_period"]["card_payment"]["USD"] == Decimal("500")
        types = {c.description: c.commitment_type for c in result["finite_commitments"]}
        assert types["Repair"] == "one_time"


class TestCoverage:
    @pytest.mark.parametrize(
        ("income", "commitments", "verdict"),
        [
            ("100", "50", "sufficient"),
            ("100", "95", "tight"),
            ("100", "100", "tight"),
            ("100", "101", "insufficient"),
            ("0", "10", "unknown"),
        ],
    )
    def test_thresholds(self, income, commitments, verdict):
        assert (
            ScheduledTransactionService._coverage(Decimal(income), Decimal(commitments))
            == verdict
        )


class TestFrequency:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("biweekly", (W, 2)),
            ("Bi-Weekly", (W, 2)),
            ("fortnightly", (W, 2)),
            ("monthly", (M, 1)),
        ],
    )
    def test_parse(self, name, expected):
        assert parse_frequency(name) == expected

    def test_unknown(self):
        with pytest.raises(ValueError, match="Unknown frequency"):
            parse_frequency("sometimes")


class TestExchangeRateService:
    async def test_reads_latest_rate_per_currency_against_sqlite(self, tmp_path):
        path = tmp_path / "moneywiz.sqlite"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER, Z_NAME VARCHAR)")
        conn.executemany(
            "INSERT INTO Z_PRIMARYKEY VALUES (?, ?)",
            [
                (10, "BankChequeAccount"),
                (11, "InvestmentAccount"),
                (20, "WithdrawTransaction"),
                (21, "TransferWithdrawTransaction"),
            ],
        )
        conn.execute(
            """CREATE TABLE ZSYNCOBJECT (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER,
               ZCURRENCYNAME TEXT, ZACCOUNT2 INTEGER, ZCURRENCYEXCHANGERATE REAL,
               ZORIGINALCURRENCY TEXT, ZDATE1 REAL)"""
        )
        conn.executemany(
            "INSERT INTO ZSYNCOBJECT VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 10, "USD", None, None, None, None),
                (2, 10, "CRC", None, None, None, None),
                (3, 11, "USD", None, None, None, None),
                (100, 20, None, 1, 1.0, "USD", 1000.0),
                (101, 20, None, 2, 520.0, "CRC", 1000.0),
                (102, 20, None, 2, 505.0, "CRC", 2000.0),  # latest CRC
                # Crypto bought in a USD account: not a USD rate.
                (103, 20, None, 3, 0.998, "BTC", 3000.0),
                # A CRC -> CRC transfer carries rate 1 between its accounts.
                (104, 21, None, 2, 1.0, "CRC", 4000.0),
            ],
        )
        conn.commit()
        conn.close()

        db = DatabaseManager(str(path), read_only=True)
        await db.initialize()
        try:
            rates = await ExchangeRateService(db).get_rates()
        finally:
            await db.close()

        assert rates.anchor == "USD"
        assert rates.rates["CRC"].units_per_anchor == Decimal("505.0")
        assert rates.convert(Decimal(1010), "CRC") == Decimal(2)

    async def test_no_accounts_gives_empty_rates(self):
        db = MagicMock(spec=DatabaseManager)
        db.get_entity_name_map = AsyncMock(return_value={})
        rates = await ExchangeRateService(db).get_rates()
        assert rates.anchor is None

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -5])
    def test_overrides_must_be_positive_and_finite(self, value):
        with pytest.raises(ValueError, match="positive finite"):
            USD_BASE.with_overrides({"CRC": value})

    async def test_base_currency_is_the_one_with_most_rate_one_rows(self, tmp_path):
        path = tmp_path / "moneywiz.sqlite"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER, Z_NAME VARCHAR)")
        conn.executemany(
            "INSERT INTO Z_PRIMARYKEY VALUES (?, ?)",
            [(10, "BankChequeAccount"), (20, "WithdrawTransaction")],
        )
        conn.execute(
            """CREATE TABLE ZSYNCOBJECT (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER,
               ZCURRENCYNAME TEXT, ZACCOUNT2 INTEGER, ZCURRENCYEXCHANGERATE REAL,
               ZORIGINALCURRENCY TEXT, ZDATE1 REAL)"""
        )
        conn.executemany(
            "INSERT INTO ZSYNCOBJECT VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 10, "USD", None, None, None, None),
                (2, 10, "CRC", None, None, None, None),
                (100, 20, None, 1, 1.0, "USD", 1000.0),
                (101, 20, None, 1, 1.0, "USD", 1100.0),
                (102, 20, None, 2, 505.0, "CRC", 1000.0),
                # The newest CRC row carries a stray rate of 1.
                (103, 20, None, 2, 1.0, "CRC", 2000.0),
            ],
        )
        conn.commit()
        conn.close()

        db = DatabaseManager(str(path), read_only=True)
        await db.initialize()
        try:
            rates = await ExchangeRateService(db).get_rates()
        finally:
            await db.close()
        assert rates.anchor == "USD"
        assert rates.rates["CRC"].units_per_anchor == Decimal("505.0")

    def test_rebase_and_overrides(self):
        crc = USD_BASE.rebase("CRC")
        assert crc.convert(Decimal(2), "USD") == Decimal(1000)
        assert USD_BASE.with_overrides({"crc": 400}).convert(Decimal(800), "CRC") == 2
        with pytest.raises(ValueError, match="positive"):
            USD_BASE.with_overrides({"CRC": 0})
