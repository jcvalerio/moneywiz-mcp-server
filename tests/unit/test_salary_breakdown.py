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
) -> ScheduledTransactionModel:
    return ScheduledTransactionModel(
        id=description,
        description=description,
        amount=Decimal(amount),
        currency=currency,
        account_id="1",
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


@pytest.fixture
def make_service(monkeypatch):
    def _make(schedules, rates=USD_BASE):
        service = ScheduledTransactionService(MagicMock(spec=DatabaseManager))
        service.get_scheduled_transactions = AsyncMock(return_value=schedules)
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
    async def test_transfers_are_allocations_not_commitments(self, make_service):
        service = make_service(
            [
                deposit("Salary", "1000", "USD"),
                bill("Rent", "-400", "USD"),
                transfer("Credit card payment", "-900", "USD"),
                transfer("To savings", "-100", "USD"),
            ]
        )
        result = await breakdown(service, planning_horizon_months=1)
        assert result["total_commitments_in_period"]["USD"] == Decimal("400")
        assert result["scheduled_transfers_in_period"]["USD"] == Decimal("1000")
        assert result["coverage_analysis"] == "sufficient"
        descriptions = {c.description for c in result["infinite_commitments"]}
        assert descriptions == {"Rent"}

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
            [(10, "BankChequeAccount"), (11, "InvestmentAccount")],
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
                (100, 99, None, 1, 1.0, "USD", 1000.0),
                (101, 99, None, 2, 520.0, "CRC", 1000.0),
                (102, 99, None, 2, 505.0, "CRC", 2000.0),  # latest CRC
                # Crypto bought in a USD account: not a USD rate.
                (103, 99, None, 3, 0.998, "BTC", 3000.0),
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

    def test_rebase_and_overrides(self):
        crc = USD_BASE.rebase("CRC")
        assert crc.convert(Decimal(2), "USD") == Decimal(1000)
        assert USD_BASE.with_overrides({"crc": 400}).convert(Decimal(800), "CRC") == 2
        with pytest.raises(ValueError, match="positive"):
            USD_BASE.with_overrides({"CRC": 0})
