"""A loan's balance drops only by the principal split of each payment."""

import sqlite3

import pytest

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.services.account_service import AccountService
from moneywiz_mcp_server.services.loan_plans import loan_payment_costs

ENTITIES = [
    (10, "BankChequeAccount"),
    (11, "LoanAccount"),
    (40, "TransferWithdrawTransaction"),
    (41, "TransferDepositTransaction"),
    (60, "PaymentPlan"),
]
PRINCIPAL, INTEREST, INSURANCE = 7, 8, 9


def make_db(path, *, with_plan_table=True):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER, Z_NAME VARCHAR)")
    entities = ENTITIES if with_plan_table else ENTITIES[:-1]
    conn.executemany("INSERT INTO Z_PRIMARYKEY VALUES (?, ?)", entities)
    conn.execute(
        """CREATE TABLE ZSYNCOBJECT (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER,
           ZNAME VARCHAR, ZCURRENCYNAME VARCHAR, ZARCHIVED INTEGER,
           ZOPENINGBALANCE REAL, ZACCOUNT2 INTEGER, ZAMOUNT1 REAL,
           ZLOANACCOUNT INTEGER, ZCATEGORYPRINCIPAL INTEGER,
           ZCATEGORYINTEREST INTEGER)"""
    )
    conn.execute(
        """CREATE TABLE ZCATEGORYASSIGMENT (Z_PK INTEGER PRIMARY KEY,
           ZTRANSACTION INTEGER, ZCATEGORY INTEGER, ZAMOUNT REAL)"""
    )
    obj = "INSERT INTO ZSYNCOBJECT VALUES (?,?,?,?,?,?,?,?,?,?,?)"
    rows = [
        (1, 10, "Bank", "USD", 0, 2000.0, None, None, None, None, None),
        # A loan with a plan, and one without.
        (2, 11, "Planned loan", "USD", 0, -1000.0, None, None, None, None, None),
        (3, 11, "Plain loan", "USD", 0, -500.0, None, None, None, None, None),
        (4, 60, None, None, None, None, None, None, 2, PRINCIPAL, INTEREST),
        # Planned loan: a 300 payment split 250 principal, 40 interest,
        # 10 insurance; then a 100 payment that is all principal.
        (100, 40, None, "USD", None, None, 1, -300.0, None, None, None),
        (101, 41, None, "USD", None, None, 2, 300.0, None, None, None),
        (102, 40, None, "USD", None, None, 1, -100.0, None, None, None),
        (103, 41, None, "USD", None, None, 2, 100.0, None, None, None),
        # Plain loan: a categorised payment still counts in full.
        (104, 40, None, "USD", None, None, 1, -100.0, None, None, None),
        (105, 41, None, "USD", None, None, 3, 100.0, None, None, None),
    ]
    if not with_plan_table:
        rows = [r for r in rows if r[1] != 60]
    conn.executemany(obj, rows)
    conn.executemany(
        "INSERT INTO ZCATEGORYASSIGMENT VALUES (?,?,?,?)",
        [
            (1, 101, PRINCIPAL, 250.0),
            (2, 101, INTEREST, 40.0),
            (3, 101, INSURANCE, 10.0),
            (4, 103, PRINCIPAL, 100.0),
            (5, 105, INTEREST, 100.0),
            # The bank side of a payment carries splits too; it's not a loan.
            (6, 100, INTEREST, -40.0),
        ],
    )
    conn.commit()
    conn.close()


async def open_db(path):
    db = DatabaseManager(str(path), read_only=True)
    await db.initialize()
    return db


async def test_only_principal_lowers_a_planned_loan(tmp_path):
    make_db(tmp_path / "m.sqlite")
    db = await open_db(tmp_path / "m.sqlite")
    try:
        assert await loan_payment_costs(db) == {2: pytest.approx(50.0)}
        accounts = {a["name"]: a for a in await AccountService(db).list_accounts()}
    finally:
        await db.close()
    # -1000 + 300 + 100 - 50 (interest and insurance are expenses)
    assert accounts["Planned loan"]["balance"] == pytest.approx(-650.0)
    # No plan: no principal category to go by, so payments count in full.
    assert accounts["Plain loan"]["balance"] == pytest.approx(-400.0)
    assert accounts["Bank"]["balance"] == pytest.approx(1500.0)


async def test_databases_without_payment_plans_are_unchanged(tmp_path):
    make_db(tmp_path / "m.sqlite", with_plan_table=False)
    db = await open_db(tmp_path / "m.sqlite")
    try:
        assert await loan_payment_costs(db) == {}
        accounts = {a["name"]: a for a in await AccountService(db).list_accounts()}
    finally:
        await db.close()
    assert accounts["Planned loan"]["balance"] == pytest.approx(-600.0)
