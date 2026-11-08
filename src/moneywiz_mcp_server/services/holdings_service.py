"""Balances of Investment and Forex accounts, holdings included.

Summing transaction amounts (the balance formula for bank accounts) gives
only part of these accounts:

- **Investment accounts** (stocks, funds) hold cash plus shares
  (InvestmentHolding). Cash is the opening balance plus every transaction
  amount (a purchase lowers it). Shares are the opening shares, plus shares
  bought, minus shares sold, plus shares received and minus shares given in
  exchanges; they're valued at the holding's latest price (ZPRICEPERSHARE).

- **Forex accounts** (crypto exchanges and wallets) hold several currencies.
  Each transaction carries the currency it moved (ZORIGINALCURRENCY) and the
  quantity (ZORIGINALAMOUNT), while ZAMOUNT1 is its value in the account
  currency when it happened, so summing ZAMOUNT1 says nothing about what is
  held now. The quantity per currency is the sum of the quantities moved
  plus exchanges between holdings; each currency is valued at the price of
  the account's holding with that symbol, and the account currency at 1.

Prices are MoneyWiz's latest, in the account's currency. A position without
a price is valued at 0 and counted, so the caller can say so.
"""

from dataclasses import dataclass
from decimal import Decimal
import logging
from typing import Any

from moneywiz_mcp_server.database.connection import DatabaseManager

logger = logging.getLogger(__name__)

ZERO = Decimal("0")
# Quantities below this are rounding leftovers, not positions.
MIN_QUANTITY = Decimal("0.00000001")
EXCHANGE_ENTITY_NAME = "InvestmentExchangeTransaction"


@dataclass(frozen=True)
class AccountValuation:
    """What an Investment or Forex account holds."""

    cash: Decimal | None  # Forex: the account currency held; None = use the sum
    holdings_value: Decimal
    without_price: int  # positions with no price (valued at 0)


def _dec(value: object) -> Decimal:
    return Decimal(str(value)) if value is not None else ZERO


class HoldingsValuer:
    """Values every Investment and Forex account in one pass."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def value_accounts(self) -> dict[int, AccountValuation] | None:
        """Valuation per account Z_PK, or None if holdings can't be read."""
        entity_map = await self.db_manager.get_entity_name_map()
        try:
            holdings = await self._holdings(entity_map)
            exchange_moves = await self._exchange_moves(entity_map, holdings)
            out = await self._investment_accounts(entity_map, holdings, exchange_moves)
            out.update(await self._forex_accounts(entity_map, holdings, exchange_moves))
            return out
        except Exception:
            logger.exception(
                "Could not value investment holdings; investment and forex "
                "balances fall back to the sum of their transactions"
            )
            return None

    async def _holdings(self, entity_map: dict[str, int]) -> list[dict[str, Any]]:
        ent = entity_map.get("InvestmentHolding")
        if ent is None:
            return []
        return await self.db_manager.execute_query(
            "SELECT Z_PK, ZINVESTMENTACCOUNT, ZSYMBOL, ZOPENNINGNUMBEROFSHARES, "
            "ZPRICEPERSHARE FROM ZSYNCOBJECT WHERE Z_ENT = ?",
            (ent,),
        )

    async def _exchange_moves(
        self, entity_map: dict[str, int], holdings: list[dict[str, Any]]
    ) -> dict[int, Decimal]:
        """Net quantity each holding gained (+) or gave (-) in exchanges."""
        ent = entity_map.get(EXCHANGE_ENTITY_NAME)
        moves: dict[int, Decimal] = {h["Z_PK"]: ZERO for h in holdings}
        if ent is None:
            return moves
        for row in await self.db_manager.execute_query(
            "SELECT ZFROMINVESTMENTHOLDING, ZFROMNUMBEROFSHARES, "
            "ZTOINVESTMENTHOLDING, ZTONUMBEROFSHARES FROM ZSYNCOBJECT "
            "WHERE Z_ENT = ?",
            (ent,),
        ):
            given, received = row["ZFROMINVESTMENTHOLDING"], row["ZTOINVESTMENTHOLDING"]
            if given in moves:
                moves[given] -= abs(_dec(row["ZFROMNUMBEROFSHARES"]))
            if received in moves:
                moves[received] += abs(_dec(row["ZTONUMBEROFSHARES"]))
        return moves

    async def _investment_accounts(
        self,
        entity_map: dict[str, int],
        holdings: list[dict[str, Any]],
        moves: dict[int, Decimal],
    ) -> dict[int, AccountValuation]:
        account_ent = entity_map.get("InvestmentAccount")
        if account_ent is None or not holdings:
            return {}
        accounts = {
            r["Z_PK"]
            for r in await self.db_manager.execute_query(
                "SELECT Z_PK FROM ZSYNCOBJECT WHERE Z_ENT = ?", (account_ent,)
            )
        }
        shares = {h["Z_PK"]: _dec(h["ZOPENNINGNUMBEROFSHARES"]) for h in holdings}
        for name, sign in (
            ("InvestmentBuyTransaction", 1),
            ("InvestmentSellTransaction", -1),
        ):
            ent = entity_map.get(name)
            if ent is None:
                continue
            for row in await self.db_manager.execute_query(
                "SELECT ZINVESTMENTHOLDING, ZNUMBEROFSHARES FROM ZSYNCOBJECT "
                "WHERE Z_ENT = ? AND ZINVESTMENTHOLDING IS NOT NULL",
                (ent,),
            ):
                if row["ZINVESTMENTHOLDING"] in shares:
                    shares[row["ZINVESTMENTHOLDING"]] += sign * abs(
                        _dec(row["ZNUMBEROFSHARES"])
                    )
        positions: dict[int, list[tuple[Decimal, object]]] = {}
        for h in holdings:
            if h["ZINVESTMENTACCOUNT"] in accounts:
                quantity = shares[h["Z_PK"]] + moves[h["Z_PK"]]
                positions.setdefault(h["ZINVESTMENTACCOUNT"], []).append(
                    (quantity, h["ZPRICEPERSHARE"])
                )
        return {
            account: self._value(None, items) for account, items in positions.items()
        }

    async def _forex_accounts(
        self,
        entity_map: dict[str, int],
        holdings: list[dict[str, Any]],
        exchange_moves: dict[int, Decimal],
    ) -> dict[int, AccountValuation]:
        account_ent = entity_map.get("ForexAccount")
        if account_ent is None:
            return {}
        accounts = {
            r["Z_PK"]: r
            for r in await self.db_manager.execute_query(
                "SELECT Z_PK, ZCURRENCYNAME, ZOPENINGBALANCE FROM ZSYNCOBJECT "
                "WHERE Z_ENT = ?",
                (account_ent,),
            )
        }
        if not accounts:
            return {}
        exchange_ent = entity_map.get(EXCHANGE_ENTITY_NAME)
        placeholders = ",".join("?" for _ in accounts)
        rows = await self.db_manager.execute_query(
            "SELECT ZACCOUNT2, Z_ENT, ZAMOUNT1, ZORIGINALCURRENCY, ZORIGINALAMOUNT "  # nosec B608 - placeholders only
            f"FROM ZSYNCOBJECT WHERE ZACCOUNT2 IN ({placeholders}) "
            "AND ZAMOUNT1 IS NOT NULL",
            tuple(accounts),
        )

        quantities: dict[int, dict[str, Decimal]] = {pk: {} for pk in accounts}
        for pk, row in accounts.items():
            base = row["ZCURRENCYNAME"] or "USD"
            quantities[pk][base] = _dec(row["ZOPENINGBALANCE"])
        for row in rows:
            if row["Z_ENT"] == exchange_ent:
                continue  # counted through the holdings it moves
            pk = row["ZACCOUNT2"]
            base = accounts[pk]["ZCURRENCYNAME"] or "USD"
            currency = row["ZORIGINALCURRENCY"] or base
            amount = _dec(row["ZAMOUNT1"])
            if currency == base or row["ZORIGINALAMOUNT"] is None:
                quantity = amount
            else:
                # ZORIGINALAMOUNT's sign isn't consistent across transaction
                # types (MoneyWiz 3 stores some incoming transfers with a
                # negative original amount), so the direction is the sign of
                # the account amount; with no amount, the original's sign.
                original = _dec(row["ZORIGINALAMOUNT"])
                quantity = abs(original)
                if amount < 0 or (amount == 0 and original < 0):
                    quantity = -quantity
            bucket = quantities[pk]
            bucket[currency] = bucket.get(currency, ZERO) + quantity

        prices: dict[int, dict[str, object]] = {}
        for h in holdings:
            pk = h["ZINVESTMENTACCOUNT"]
            if pk in accounts and h["ZSYMBOL"]:
                prices.setdefault(pk, {})[h["ZSYMBOL"]] = h["ZPRICEPERSHARE"]
                bucket = quantities[pk]
                bucket[h["ZSYMBOL"]] = (
                    bucket.get(h["ZSYMBOL"], ZERO) + exchange_moves[h["Z_PK"]]
                )

        out = {}
        for pk, bucket in quantities.items():
            base = accounts[pk]["ZCURRENCYNAME"] or "USD"
            items = [
                (quantity, prices.get(pk, {}).get(currency))
                for currency, quantity in bucket.items()
                if currency != base
            ]
            out[pk] = self._value(bucket.get(base, ZERO), items)
        return out

    @staticmethod
    def _value(
        cash: Decimal | None, items: list[tuple[Decimal, object]]
    ) -> AccountValuation:
        value = ZERO
        unpriced = 0
        for quantity, price in items:
            if abs(quantity) < MIN_QUANTITY:
                continue
            if price:
                value += quantity * _dec(price)
            else:
                unpriced += 1
        return AccountValuation(cash, value, unpriced)
