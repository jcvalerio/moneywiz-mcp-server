#!/usr/bin/env python3
"""Create a test MoneyWiz database with realistic sample data for CI/CD testing."""

from datetime import datetime, timedelta
from pathlib import Path
import sqlite3


def create_test_database(db_path: str) -> None:
    """Create a test MoneyWiz database with sample data."""

    # Remove existing database if it exists
    db_file = Path(db_path)
    if db_file.exists():
        db_file.unlink()

    # Create database connection
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create Core Data metadata tables
        cursor.execute("""
        CREATE TABLE Z_PRIMARYKEY (
            Z_ENT INTEGER PRIMARY KEY,
            Z_NAME TEXT,
            Z_SUPER INTEGER,
            Z_MAX INTEGER
        )
        """)

        # Insert entity metadata
        entities = [
            (10, "BankChequeAccount", 0, 2),
            (11, "BankSavingAccount", 0, 1),
            (12, "CashAccount", 0, 1),
            (13, "CreditCardAccount", 0, 1),
            (19, "Category", 0, 10),
            (28, "Payee", 0, 5),
            (37, "DepositTransaction", 0, 20),
            (47, "WithdrawTransaction", 0, 30),
        ]

        cursor.executemany(
            """
        INSERT INTO Z_PRIMARYKEY (Z_ENT, Z_NAME, Z_SUPER, Z_MAX)
        VALUES (?, ?, ?, ?)
        """,
            entities,
        )

        # Create main ZSYNCOBJECT table (Core Data equivalent)
        cursor.execute("""
        CREATE TABLE ZSYNCOBJECT (
            Z_PK INTEGER PRIMARY KEY,
            Z_ENT INTEGER,
            Z_OPT INTEGER,
            ZOPENINGBALANCE REAL,
            ZNAME TEXT,
            ZNAME2 TEXT,
            ZCURRENCYNAME TEXT,
            ZARCHIVED INTEGER DEFAULT 0,
            ZINSTITUTIONNAME TEXT,
            ZLASTFOURDIGITS TEXT,
            ZOBJECTCREATIONDATE REAL,
            ZAMOUNT1 REAL,
            ZDATE1 REAL,
            ZDESC2 TEXT,
            ZDESCRIPTION TEXT,
            ZNOTES1 TEXT,
            ZRECONCILED INTEGER DEFAULT 0,
            ZACCOUNT2 INTEGER,
            ZPAYEE2 INTEGER,
            ZPAYEE INTEGER,
            ZDATEADDED REAL
        )
        """)

        # Create category assignment table (note: missing 'N' is intentional - MoneyWiz quirk)
        cursor.execute("""
        CREATE TABLE ZCATEGORYASSIGMENT (
            Z_PK INTEGER PRIMARY KEY,
            ZTRANSACTION INTEGER,
            ZCATEGORY INTEGER
        )
        """)

        # Insert sample accounts
        current_timestamp = (datetime.now() - datetime(2001, 1, 1)).total_seconds()

        accounts = [
            (
                1,
                10,
                1,
                1500.50,
                "Test Checking",
                None,
                "USD",
                0,
                "Test Bank",
                "1234",
                current_timestamp,
            ),
            (
                2,
                11,
                1,
                5000.00,
                "Test Savings",
                None,
                "USD",
                0,
                "Test Bank",
                "5678",
                current_timestamp,
            ),
            (
                3,
                12,
                1,
                200.00,
                "Cash Wallet",
                None,
                "USD",
                0,
                "",
                "",
                current_timestamp,
            ),
            (
                4,
                13,
                1,
                -850.75,
                "Test Credit Card",
                None,
                "USD",
                0,
                "Credit Union",
                "9012",
                current_timestamp,
            ),
        ]

        for account in accounts:
            cursor.execute(
                """
            INSERT INTO ZSYNCOBJECT (
                Z_PK, Z_ENT, Z_OPT, ZOPENINGBALANCE, ZNAME, ZNAME2, ZCURRENCYNAME,
                ZARCHIVED, ZINSTITUTIONNAME, ZLASTFOURDIGITS, ZOBJECTCREATIONDATE
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                account,
            )

        # Insert sample categories
        categories = [
            (
                101,
                19,
                1,
                None,
                "Food & Dining",
                "Food & Dining",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                102,
                19,
                1,
                None,
                "Groceries",
                "Groceries",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                103,
                19,
                1,
                None,
                "Transportation",
                "Transportation",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                104,
                19,
                1,
                None,
                "Shopping",
                "Shopping",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                105,
                19,
                1,
                None,
                "Entertainment",
                "Entertainment",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                106,
                19,
                1,
                None,
                "Bills & Utilities",
                "Bills & Utilities",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                107,
                19,
                1,
                None,
                "Income",
                "Income",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
        ]

        for category in categories:
            cursor.execute(
                """
            INSERT INTO ZSYNCOBJECT (
                Z_PK, Z_ENT, Z_OPT, ZOPENINGBALANCE, ZNAME, ZNAME2, ZCURRENCYNAME,
                ZARCHIVED, ZINSTITUTIONNAME, ZLASTFOURDIGITS, ZOBJECTCREATIONDATE
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                category,
            )

        # Insert sample payees
        payees = [
            (
                201,
                28,
                1,
                None,
                "Whole Foods",
                "Whole Foods",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                202,
                28,
                1,
                None,
                "Shell Gas Station",
                "Shell Gas Station",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                203,
                28,
                1,
                None,
                "Netflix",
                "Netflix",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                204,
                28,
                1,
                None,
                "Salary Deposit",
                "Salary Deposit",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
            (
                205,
                28,
                1,
                None,
                "Electric Company",
                "Electric Company",
                None,
                0,
                None,
                None,
                current_timestamp,
            ),
        ]

        for payee in payees:
            cursor.execute(
                """
            INSERT INTO ZSYNCOBJECT (
                Z_PK, Z_ENT, Z_OPT, ZOPENINGBALANCE, ZNAME, ZNAME2, ZCURRENCYNAME,
                ZARCHIVED, ZINSTITUTIONNAME, ZLASTFOURDIGITS, ZOBJECTCREATIONDATE
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                payee,
            )

        # Insert sample transactions
        transactions = []
        current_date = datetime.now()

        # Generate transactions for the last 3 months
        for days_ago in range(90):
            transaction_date = current_date - timedelta(days=days_ago)
            core_data_timestamp = (
                transaction_date - datetime(2001, 1, 1)
            ).total_seconds()

            if days_ago % 7 == 0:  # Weekly salary
                transactions.append(
                    (
                        1000 + days_ago,
                        37,
                        1,
                        None,
                        None,
                        None,
                        None,
                        0,
                        None,
                        None,
                        current_timestamp,
                        3000.00,
                        core_data_timestamp,
                        "Salary Deposit",
                        "Salary Deposit",
                        "Bi-weekly salary",
                        1,
                        1,
                        204,
                        204,
                        core_data_timestamp,
                    )
                )

            if days_ago % 3 == 0:  # Groceries every 3 days
                transactions.append(
                    (
                        2000 + days_ago,
                        47,
                        1,
                        None,
                        None,
                        None,
                        None,
                        0,
                        None,
                        None,
                        current_timestamp,
                        -85.50,
                        core_data_timestamp,
                        "Grocery Shopping",
                        "Grocery Shopping",
                        "Weekly groceries",
                        0,
                        1,
                        201,
                        201,
                        core_data_timestamp,
                    )
                )

            if days_ago % 5 == 0:  # Gas every 5 days
                transactions.append(
                    (
                        3000 + days_ago,
                        47,
                        1,
                        None,
                        None,
                        None,
                        None,
                        0,
                        None,
                        None,
                        current_timestamp,
                        -45.20,
                        core_data_timestamp,
                        "Gas Fill-up",
                        "Gas Fill-up",
                        None,
                        0,
                        1,
                        202,
                        202,
                        core_data_timestamp,
                    )
                )

        for transaction in transactions:
            cursor.execute(
                """
            INSERT INTO ZSYNCOBJECT (
                Z_PK, Z_ENT, Z_OPT, ZOPENINGBALANCE, ZNAME, ZNAME2, ZCURRENCYNAME,
                ZARCHIVED, ZINSTITUTIONNAME, ZLASTFOURDIGITS, ZOBJECTCREATIONDATE,
                ZAMOUNT1, ZDATE1, ZDESC2, ZDESCRIPTION, ZNOTES1, ZRECONCILED, ZACCOUNT2, ZPAYEE2, ZPAYEE, ZDATEADDED
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                transaction,
            )

        # Insert category assignments
        category_assignments = []
        assignment_id = 1

        # Assign categories to transactions
        for days_ago in range(90):
            if days_ago % 7 == 0:  # Salary -> Income
                category_assignments.append((assignment_id, 1000 + days_ago, 107))
                assignment_id += 1

            if days_ago % 3 == 0:  # Groceries -> Food & Dining
                category_assignments.append((assignment_id, 2000 + days_ago, 101))
                assignment_id += 1

            if days_ago % 5 == 0:  # Gas -> Transportation
                category_assignments.append((assignment_id, 3000 + days_ago, 103))
                assignment_id += 1

        cursor.executemany(
            """
        INSERT INTO ZCATEGORYASSIGMENT (Z_PK, ZTRANSACTION, ZCATEGORY)
        VALUES (?, ?, ?)
        """,
            category_assignments,
        )

        # Commit all changes
        conn.commit()
        print(f"✅ Test database created at {db_path}")
        print(f"   - {len(accounts)} accounts")
        print(f"   - {len(categories)} categories")
        print(f"   - {len(payees)} payees")
        print(f"   - {len(transactions)} transactions")
        print(f"   - {len(category_assignments)} category assignments")

    except Exception as e:
        print(f"❌ Error creating test database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Create test database in fixtures directory
    fixtures_dir = Path(__file__).parent
    db_path = fixtures_dir / "sample_moneywiz.sqlite"
    create_test_database(str(db_path))
