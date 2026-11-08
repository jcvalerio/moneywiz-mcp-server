"""Investment and Forex account balances include what they hold."""

from decimal import Decimal
import sqlite3

import pytest

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.services.account_service import AccountService
from moneywiz_mcp_server.services.holdings_service import (
    AccountValuation,
    HoldingsValuer,
)

ENTITIES = [
    (10, "BankChequeAccount"),
    (11, "InvestmentAccount"),
    (12, "ForexAccount"),
    (30, "InvestmentHolding"),
    (40, "WithdrawTransaction"),
    (41, "InvestmentBuyTransaction"),
    (42, "InvestmentSellTransaction"),
    (43, "InvestmentExchangeTransaction"),
    (44, "DepositTransaction"),
    (45, "TransferDepositTransaction"),
    (46, "TransferWithdrawTransaction"),
]
COLUMNS = (
    "Z_PK",
    "Z_ENT",
    "ZNAME",
    "ZCURRENCYNAME",
    "ZARCHIVED",
    "ZOPENINGBALANCE",
    "ZACCOUNT2",
    "ZAMOUNT1",
    "ZORIGINALCURRENCY",
    "ZORIGINALAMOUNT",
    "ZINVESTMENTACCOUNT",
    "ZSYMBOL",
    "ZOPENNINGNUMBEROFSHARES",
    "ZPRICEPERSHARE",
    "ZINVESTMENTHOLDING",
    "ZNUMBEROFSHARES",
    "ZFROMINVESTMENTHOLDING",
    "ZFROMNUMBEROFSHARES",
    "ZTOINVESTMENTHOLDING",
    "ZTONUMBEROFSHARES",
)


def make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER, Z_NAME VARCHAR)")
    conn.executemany("INSERT INTO Z_PRIMARYKEY VALUES (?, ?)", ENTITIES)
    conn.execute(f"CREATE TABLE ZSYNCOBJECT ({', '.join(COLUMNS)}, PRIMARY KEY (Z_PK))")

    def add(**values):
        row = dict.fromkeys(COLUMNS)
        row.update(values)
        conn.execute(
            f"INSERT INTO ZSYNCOBJECT VALUES ({','.join('?' * len(COLUMNS))})",
            tuple(row.values()),
        )

    def account(pk, ent, name):
        add(
            Z_PK=pk,
            Z_ENT=ent,
            ZNAME=name,
            ZCURRENCYNAME="USD",
            ZARCHIVED=0,
            ZOPENINGBALANCE=0.0,
        )

    account(1, 10, "Bank")
    account(2, 11, "Broker")
    account(3, 12, "Exchange")

    # Broker: deposit 300, buy 10 shares of a 25 stock (2 opening shares),
    # sell 4; a bond with no price.
    add(
        Z_PK=100,
        Z_ENT=30,
        ZINVESTMENTACCOUNT=2,
        ZSYMBOL="ABC",
        ZOPENNINGNUMBEROFSHARES=2.0,
        ZPRICEPERSHARE=25.0,
    )
    add(
        Z_PK=101,
        Z_ENT=30,
        ZINVESTMENTACCOUNT=2,
        ZSYMBOL="BOND",
        ZOPENNINGNUMBEROFSHARES=1.0,
        ZPRICEPERSHARE=None,
    )
    add(Z_PK=200, Z_ENT=44, ZACCOUNT2=2, ZAMOUNT1=300.0)
    add(
        Z_PK=201,
        Z_ENT=41,
        ZACCOUNT2=2,
        ZAMOUNT1=-250.0,
        ZINVESTMENTHOLDING=100,
        ZNUMBEROFSHARES=10.0,
    )
    add(
        Z_PK=202,
        Z_ENT=42,
        ZACCOUNT2=2,
        ZAMOUNT1=100.0,
        ZINVESTMENTHOLDING=100,
        ZNUMBEROFSHARES=-4.0,
    )

    # Exchange (crypto): coins arrive as transfers in their own currency;
    # ZAMOUNT1 is their USD value at the time, ZORIGINALAMOUNT the quantity.
    add(
        Z_PK=110,
        Z_ENT=30,
        ZINVESTMENTACCOUNT=3,
        ZSYMBOL="BTC",
        ZOPENNINGNUMBEROFSHARES=0.0,
        ZPRICEPERSHARE=100000.0,
    )
    add(
        Z_PK=111,
        Z_ENT=30,
        ZINVESTMENTACCOUNT=3,
        ZSYMBOL="USDT",
        ZOPENNINGNUMBEROFSHARES=0.0,
        ZPRICEPERSHARE=1.0,
    )
    add(
        Z_PK=112,
        Z_ENT=30,
        ZINVESTMENTACCOUNT=3,
        ZSYMBOL="NEW",
        ZOPENNINGNUMBEROFSHARES=0.0,
        ZPRICEPERSHARE=None,
    )
    # 0.03 BTC in, 0.01 BTC out (stored with a positive quantity: the
    # direction comes from the amount's sign).
    add(
        Z_PK=210,
        Z_ENT=45,
        ZACCOUNT2=3,
        ZAMOUNT1=1500.0,
        ZORIGINALCURRENCY="BTC",
        ZORIGINALAMOUNT=0.03,
    )
    add(
        Z_PK=211,
        Z_ENT=46,
        ZACCOUNT2=3,
        ZAMOUNT1=-900.0,
        ZORIGINALCURRENCY="BTC",
        ZORIGINALAMOUNT=0.01,
    )
    # Swap 0.01 BTC for 1000 USDT, then sell 400 USDT for 400 USD cash.
    add(
        Z_PK=212,
        Z_ENT=43,
        ZACCOUNT2=3,
        ZAMOUNT1=-500.0,
        ZFROMINVESTMENTHOLDING=110,
        ZFROMNUMBEROFSHARES=-0.01,
        ZTOINVESTMENTHOLDING=111,
        ZTONUMBEROFSHARES=1000.0,
    )
    add(
        Z_PK=213,
        Z_ENT=46,
        ZACCOUNT2=3,
        ZAMOUNT1=-400.0,
        ZORIGINALCURRENCY="USDT",
        ZORIGINALAMOUNT=-400.0,
    )
    add(
        Z_PK=214,
        Z_ENT=44,
        ZACCOUNT2=3,
        ZAMOUNT1=400.0,
        ZORIGINALCURRENCY="USD",
        ZORIGINALAMOUNT=400.0,
    )
    # A coin with no price yet.
    add(
        Z_PK=215,
        Z_ENT=44,
        ZACCOUNT2=3,
        ZAMOUNT1=5.0,
        ZORIGINALCURRENCY="NEW",
        ZORIGINALAMOUNT=50.0,
    )
    conn.commit()
    conn.close()


@pytest.fixture
async def db(tmp_path):
    path = tmp_path / "moneywiz.sqlite"
    make_db(path)
    manager = DatabaseManager(str(path), read_only=True)
    await manager.initialize()
    yield manager
    await manager.close()


async def test_investment_holdings_are_valued_at_the_latest_price(db):
    values = await HoldingsValuer(db).value_accounts()
    # (2 + 10 - 4) x 25 = 200; the bond has no price.
    assert values[2] == AccountValuation(None, Decimal("200.0"), 2, 1)


async def test_forex_accounts_are_valued_per_currency_held(db):
    values = await HoldingsValuer(db).value_accounts()
    # BTC: 0.03 - 0.01 - 0.01 (swap) = 0.01 x 100000 = 1000
    # USDT: 1000 - 400 = 600 x 1 = 600; NEW: 50 without a price.
    assert values[3] == AccountValuation(Decimal("400.0"), Decimal("1600.0"), 3, 1)
    assert 1 not in values


async def test_account_balances_include_holdings(db):
    accounts = {a["name"]: a for a in await AccountService(db).list_accounts()}
    broker = accounts["Broker"]
    assert broker["cash_balance"] == pytest.approx(150.0)  # 300 - 250 + 100
    assert broker["holdings_value"] == pytest.approx(200.0)
    assert broker["balance"] == pytest.approx(350.0)
    assert broker["holdings_without_price"] == 1
    exchange = accounts["Exchange"]
    # The USD sum of its transactions (205) means nothing for a forex account.
    assert exchange["cash_balance"] == pytest.approx(400.0)
    assert exchange["balance"] == pytest.approx(2000.0)
    bank = accounts["Bank"]
    assert (bank["balance"], bank["holdings_value"]) == (0.0, 0.0)


async def test_get_account_matches_its_response_model(db):
    from moneywiz_mcp_server.models.responses import AccountDetailResponse

    service = AccountService(db)
    broker = next(a for a in await service.list_accounts() if a["name"] == "Broker")
    detail = AccountDetailResponse(**await service.get_account(broker["id"]))
    assert detail.balance == pytest.approx(350.0)
    assert (detail.last_four_digits, detail.account_info) == ("", "")


async def test_no_holding_entities_means_no_valuations(tmp_path):
    path = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER, Z_NAME VARCHAR)")
    conn.execute("CREATE TABLE ZSYNCOBJECT (Z_PK INTEGER PRIMARY KEY, Z_ENT INT)")
    conn.commit()
    conn.close()
    manager = DatabaseManager(str(path), read_only=True)
    await manager.initialize()
    try:
        assert await HoldingsValuer(manager).value_accounts() == {}
    finally:
        await manager.close()
