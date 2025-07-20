#!/usr/bin/env python3
"""Analyze MoneyWiz database schema for missing data elements."""

import os
from pathlib import Path
import sqlite3


def analyze_database():
    """Analyze MoneyWiz database for category hierarchies and missing data."""

    # Load database path from .env if it exists
    env_path = Path(".env")
    db_path = None

    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith("MONEYWIZ_DB_PATH="):
                    db_path = line.split("=", 1)[1].strip().strip('"')
                    break

    if not db_path:
        # Try to find database
        home = Path.home()
        possible_paths = [
            home / "Library/Containers/com.moneywiz.mac/Data/Documents",
            home / "Library/Containers/com.moneywiz.personalfinance/Data/Documents",
            home / "Library/Containers/com.moneywiz.personalfinance-setapp/Data/Documents",
            home / "Library/Application Support/MoneyWiz",
        ]

        for base_path in possible_paths:
            if base_path.exists():
                for db_file in base_path.glob("**/*.sqlite*"):
                    if db_file.is_file() and db_file.stat().st_size > 0:
                        db_path = str(db_file)
                        break
            if db_path:
                break

    if not db_path or not os.path.exists(db_path):
        print("Database not found. Please run setup_env.py first.")
        return

    print(f"Using database: {db_path}")

    # Connect and analyze
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("\n=== DATABASE SCHEMA ANALYSIS ===")
    cursor.execute("PRAGMA table_info(ZSYNCOBJECT)")
    columns = cursor.fetchall()
    print("ZSYNCOBJECT columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")

    print("\n=== CATEGORY ENTITY ANALYSIS ===")
    cursor.execute("""
    SELECT * FROM ZSYNCOBJECT
    WHERE Z_ENT = 19
    LIMIT 3
    """)

    categories = cursor.fetchall()
    for i, cat in enumerate(categories):
        print(f"Category {i+1}:")
        for key in cat:
            value = cat[key]
            if value is not None and str(value).strip() != "":
                print(f"  {key}: {value}")
        print()

    print("\n=== SAMPLE TRANSACTION WITH CATEGORY ===")
    cursor.execute("""
    SELECT t.Z_PK, t.ZDESC2, t.ZAMOUNT1, ca.ZCATEGORY, c.ZNAME2 as category_name
    FROM ZSYNCOBJECT t
    LEFT JOIN ZCATEGORYASSIGMENT ca ON ca.ZTRANSACTION = t.Z_PK
    LEFT JOIN ZSYNCOBJECT c ON c.Z_PK = ca.ZCATEGORY AND c.Z_ENT = 19
    WHERE t.Z_ENT IN (37, 45, 46, 47)
    AND t.ZDESC2 IS NOT NULL
    AND ca.ZCATEGORY IS NOT NULL
    LIMIT 5
    """)

    sample_txns = cursor.fetchall()
    print("Sample transactions with categories:")
    for txn in sample_txns:
        print(f'  TXN {txn["Z_PK"]}: "{txn["ZDESC2"]}" Amount: {txn["ZAMOUNT1"]} Category: "{txn["category_name"]}"')

    print("\n=== TAG ANALYSIS ===")
    cursor.execute("""
    SELECT Z_PK, ZNAME, ZNAME2
    FROM ZSYNCOBJECT
    WHERE Z_ENT = 35
    LIMIT 10
    """)

    tags = cursor.fetchall()
    print(f"Found {len(tags)} tags:")
    for tag in tags:
        name = tag["ZNAME"] or tag["ZNAME2"] or "NULL"
        print(f'  ID {tag["Z_PK"]}: "{name}"')

    print("\n=== TRANSACTION-TAG RELATIONSHIPS ===")
    cursor.execute("""
    SELECT
        tt.Z_35TAGS as tag_id,
        tt.Z_36TRANSACTIONS as transaction_id,
        t.ZNAME as tag_name,
        txn.ZDESC2 as transaction_desc
    FROM Z_36TAGS tt
    LEFT JOIN ZSYNCOBJECT t ON t.Z_PK = tt.Z_35TAGS AND t.Z_ENT = 35
    LEFT JOIN ZSYNCOBJECT txn ON txn.Z_PK = tt.Z_36TRANSACTIONS
    LIMIT 10
    """)

    tag_relations = cursor.fetchall()
    print(f"Found {len(tag_relations)} tag-transaction relationships:")
    for rel in tag_relations:
        tag_name = rel["tag_name"] or "NULL"
        print(f'  Tag "{tag_name}" -> Transaction "{rel["transaction_desc"]}"')

    print("\n=== TRANSACTION FIELD ANALYSIS ===")
    cursor.execute("""
    SELECT * FROM ZSYNCOBJECT
    WHERE Z_ENT IN (37, 45, 46, 47)
    AND ZDESC2 IS NOT NULL
    LIMIT 1
    """)

    sample_txn = cursor.fetchone()
    if sample_txn:
        print("Sample transaction fields (non-null values):")
        for key in sample_txn:
            value = sample_txn[key]
            if value is not None and str(value).strip() != "":
                print(f"  {key}: {value}")

    conn.close()

if __name__ == "__main__":
    analyze_database()
