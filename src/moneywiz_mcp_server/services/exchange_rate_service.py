"""Exchange rates for presenting multi-currency amounts in one currency.

MoneyWiz records, on every transaction, ZCURRENCYEXCHANGERATE: units of the
account's currency per 1 unit of the user's base currency (base-currency
transactions have rate 1). The latest rate per currency is the rate MoneyWiz
itself is using, so it is the default; callers can override any rate.

Only deposits, withdrawals and refunds are read: a transfer's rate is
between its two accounts (a CRC -> CRC transfer has rate 1), not against the
base currency.

Native amounts are always kept: conversion only adds a combined total.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
import logging

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.services.transaction_service import ACCOUNT_ENTITY_NAMES
from moneywiz_mcp_server.utils.core_data_time import core_data_timestamp_to_datetime

logger = logging.getLogger(__name__)

SOURCE_MONEYWIZ = "moneywiz"
SOURCE_PROVIDED = "provided"

# Transaction entities whose ZCURRENCYEXCHANGERATE is against the base currency.
BASE_RATE_ENTITY_NAMES = (
    "DepositTransaction",
    "WithdrawTransaction",
    "RefundTransaction",
)


@dataclass(frozen=True)
class RateInfo:
    """Units of a currency per 1 unit of the anchor currency."""

    units_per_anchor: Decimal
    as_of: datetime | None
    source: str


@dataclass(frozen=True)
class ExchangeRates:
    """Rates relative to one anchor currency (whose own rate is 1)."""

    anchor: str | None
    rates: dict[str, RateInfo] = field(default_factory=dict)

    def has(self, currency: str) -> bool:
        return currency in self.rates

    def rebase(self, new_anchor: str) -> "ExchangeRates":
        """Express every rate per 1 unit of new_anchor.

        If new_anchor has no known rate it becomes the anchor of an otherwise
        empty table (only overrides can then fill it).
        """
        if new_anchor == self.anchor:
            return self
        pivot = self.rates.get(new_anchor)
        if pivot is None:
            return ExchangeRates(
                anchor=new_anchor,
                rates={new_anchor: RateInfo(Decimal(1), None, SOURCE_PROVIDED)},
            )
        rebased = {
            code: RateInfo(
                info.units_per_anchor / pivot.units_per_anchor, info.as_of, info.source
            )
            for code, info in self.rates.items()
        }
        rebased[new_anchor] = RateInfo(Decimal(1), pivot.as_of, pivot.source)
        return ExchangeRates(anchor=new_anchor, rates=rebased)

    def with_overrides(self, overrides: dict[str, float] | None) -> "ExchangeRates":
        """Apply caller rates, given as units of each currency per 1 anchor unit."""
        if not overrides:
            return self
        rates = dict(self.rates)
        for code, value in overrides.items():
            try:
                rate = Decimal(str(value))
            except InvalidOperation:
                raise ValueError(
                    f"Invalid exchange rate for {code}: {value!r}"
                ) from None
            if rate <= 0:
                raise ValueError(f"Exchange rate for {code} must be positive")
            rates[code.upper()] = RateInfo(rate, None, SOURCE_PROVIDED)
        return ExchangeRates(anchor=self.anchor, rates=rates)

    def convert(self, amount: Decimal, currency: str) -> Decimal | None:
        """Convert amount in currency to the anchor, or None if no rate."""
        info = self.rates.get(currency)
        if info is None or info.units_per_anchor == 0:
            return None
        return amount / info.units_per_anchor


class ExchangeRateService:
    """Reads the latest exchange rate per currency from MoneyWiz."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def get_rates(self) -> ExchangeRates:
        """Latest rate per account currency, anchored on the base currency.

        Returns an empty table (anchor None) when the database has no
        usable rates, so callers can still report native amounts.
        """
        entity_map = await self.db_manager.get_entity_name_map()
        account_ids = [entity_map[n] for n in ACCOUNT_ENTITY_NAMES if n in entity_map]
        tx_ids = [entity_map[n] for n in BASE_RATE_ENTITY_NAMES if n in entity_map]
        if not account_ids or not tx_ids:
            return ExchangeRates(anchor=None)

        placeholders = ",".join("?" for _ in account_ids)
        tx_placeholders = ",".join("?" for _ in tx_ids)
        # Latest transaction per account currency that carries a rate. SQLite
        # returns the bare columns from the row holding MAX(t.ZDATE1).
        query = f"""
            SELECT a.ZCURRENCYNAME AS currency,
                   t.ZCURRENCYEXCHANGERATE AS rate,
                   MAX(t.ZDATE1) AS date
            FROM ZSYNCOBJECT t
            JOIN ZSYNCOBJECT a ON a.Z_PK = t.ZACCOUNT2
            WHERE a.Z_ENT IN ({placeholders})
              AND t.Z_ENT IN ({tx_placeholders})
              AND a.ZCURRENCYNAME IS NOT NULL
              AND t.ZCURRENCYEXCHANGERATE > 0
              AND (t.ZORIGINALCURRENCY IS NULL
                   OR t.ZORIGINALCURRENCY = a.ZCURRENCYNAME)
              AND t.ZDATE1 IS NOT NULL
            GROUP BY a.ZCURRENCYNAME
        """  # nosec B608 - placeholders only, values are bound
        try:
            rows = await self.db_manager.execute_query(query, (*account_ids, *tx_ids))
        except Exception as e:
            logger.warning(f"Could not read exchange rates: {e}")
            return ExchangeRates(anchor=None)

        rates: dict[str, RateInfo] = {}
        for row in rows:
            currency, rate, date = row.get("currency"), row.get("rate"), row.get("date")
            if not currency or not rate:
                continue
            rates[currency] = RateInfo(
                Decimal(str(rate)),
                core_data_timestamp_to_datetime(date) if date is not None else None,
                SOURCE_MONEYWIZ,
            )

        base = next(
            (c for c, info in rates.items() if info.units_per_anchor == 1), None
        )
        if base is None:
            if rates:
                logger.warning("No base currency (rate 1) found in MoneyWiz rates")
            return ExchangeRates(anchor=None)
        return ExchangeRates(anchor=base, rates=rates)
