#!/usr/bin/env python3
"""
Deep investigation of budget schema to understand:
1. What ZBUDGETFROM/ZBUDGETTO reference
2. How to get category for a budget
3. How to calculate spent amounts from ZTRANSACTIONBUDGETLINK
"""

import asyncio
import logging

from src.moneywiz_mcp_server.config import Config
from src.moneywiz_mcp_server.database.connection import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def investigate_budgets_deep():
    """Deep investigation of budget relationships."""

    config = Config.from_env()
    db_manager = DatabaseManager(config.database_path, read_only=True)
    await db_manager.initialize()

    try:
        logger.info("=" * 70)
        logger.info("🔬 Deep Budget Schema Investigation")
        logger.info("=" * 70)

        # Phase 1: Analyze Entity 44 (Budget) in detail
        logger.info("\n📊 Phase 1: Full analysis of Entity 44 (Budget)...")

        budget_query = """
            SELECT * FROM ZSYNCOBJECT
            WHERE Z_ENT = 44
            LIMIT 10
        """
        budgets = await db_manager.execute_query(budget_query)

        logger.info(f"Found {len(budgets)} budget records (showing first 10)")

        for i, budget in enumerate(budgets[:5]):
            logger.info(f"\n  Budget {i + 1} (Z_PK={budget['Z_PK']}):")
            logger.info(f"    Amount: {budget.get('ZAMOUNT1')}")
            logger.info(
                f"    BudgetFrom: {budget.get('ZBUDGETFROM')} -> BudgetTo: {budget.get('ZBUDGETTO')}"
            )
            logger.info(f"    Date1: {budget.get('ZDATE1')}")
            logger.info(f"    ExchangeRate: {budget.get('ZCURRENCYEXCHANGERATE')}")
            logger.info(f"    Status: {budget.get('ZSTATUS1')}")

        # Phase 2: Understand what ZBUDGETFROM references
        logger.info("\n📊 Phase 2: Understanding ZBUDGETFROM/ZBUDGETTO references...")

        # Get unique ZBUDGETFROM values
        unique_from_query = """
            SELECT DISTINCT ZBUDGETFROM FROM ZSYNCOBJECT WHERE Z_ENT = 44
        """
        unique_from = await db_manager.execute_query(unique_from_query)
        from_ids = [r["ZBUDGETFROM"] for r in unique_from if r["ZBUDGETFROM"]]

        logger.info(f"Unique ZBUDGETFROM values: {from_ids[:10]}...")

        # Find what entity types these IDs belong to
        if from_ids:
            sample_id = from_ids[0]
            ref_query = """
                SELECT Z_PK, Z_ENT, ZNAME2 FROM ZSYNCOBJECT WHERE Z_PK = ?
            """
            ref_result = await db_manager.execute_query(ref_query, (sample_id,))
            if ref_result:
                ref = ref_result[0]
                logger.info(
                    f"  ZBUDGETFROM={sample_id} points to Entity {ref['Z_ENT']}, Name: {ref.get('ZNAME2')}"
                )

        # Get unique ZBUDGETTO values
        unique_to_query = """
            SELECT DISTINCT ZBUDGETTO FROM ZSYNCOBJECT WHERE Z_ENT = 44
        """
        unique_to = await db_manager.execute_query(unique_to_query)
        to_ids = [r["ZBUDGETTO"] for r in unique_to if r["ZBUDGETTO"]]

        logger.info(f"Unique ZBUDGETTO values: {to_ids[:10]}...")

        if to_ids:
            sample_id = to_ids[0]
            ref_query = """
                SELECT Z_PK, Z_ENT, ZNAME2 FROM ZSYNCOBJECT WHERE Z_PK = ?
            """
            ref_result = await db_manager.execute_query(ref_query, (sample_id,))
            if ref_result:
                ref = ref_result[0]
                logger.info(
                    f"  ZBUDGETTO={sample_id} points to Entity {ref['Z_ENT']}, Name: {ref.get('ZNAME2')}"
                )

        # Phase 3: Analyze ZCATEGORYASSIGMENT for budget-category links
        logger.info("\n📊 Phase 3: Analyzing ZCATEGORYASSIGMENT for budget links...")

        catassign_query = """
            SELECT ca.*, so.ZNAME2 as category_name
            FROM ZCATEGORYASSIGMENT ca
            LEFT JOIN ZSYNCOBJECT so ON ca.ZCATEGORY = so.Z_PK
            WHERE ca.ZBUDGET IS NOT NULL
            LIMIT 20
        """
        cat_assignments = await db_manager.execute_query(catassign_query)

        logger.info(
            f"Found {len(cat_assignments)} category assignments with budget links"
        )

        # Group by budget
        budget_categories = {}
        for ca in cat_assignments:
            budget_id = ca.get("ZBUDGET")
            if budget_id not in budget_categories:
                budget_categories[budget_id] = []
            budget_categories[budget_id].append(ca.get("category_name"))

        for budget_id, categories in list(budget_categories.items())[:5]:
            logger.info(f"  Budget {budget_id}: Categories = {categories}")

        # Phase 4: Analyze ZTRANSACTIONBUDGETLINK for spent calculations
        logger.info("\n📊 Phase 4: Analyzing ZTRANSACTIONBUDGETLINK structure...")

        tbl_query = "PRAGMA table_info(ZTRANSACTIONBUDGETLINK)"
        tbl_cols = await db_manager.execute_query(tbl_query)
        col_names = [c["name"] for c in tbl_cols]
        logger.info(f"ZTRANSACTIONBUDGETLINK columns: {col_names}")

        # Get sample transaction-budget links
        link_query = """
            SELECT tbl.*, t.ZAMOUNT1 as transaction_amount, t.ZDATE1 as transaction_date
            FROM ZTRANSACTIONBUDGETLINK tbl
            LEFT JOIN ZSYNCOBJECT t ON tbl.ZTRANSACTION = t.Z_PK
            WHERE tbl.ZBUDGET IS NOT NULL
            LIMIT 10
        """
        links = await db_manager.execute_query(link_query)

        logger.info(f"Found {len(links)} transaction-budget links")

        for link in links[:3]:
            logger.info(
                f"  Link: Budget={link.get('ZBUDGET')}, Transaction={link.get('ZTRANSACTION')}, Amount={link.get('transaction_amount')}"
            )

        # Phase 5: Calculate total spent for a budget
        logger.info("\n📊 Phase 5: Calculating spent amounts for budgets...")

        # Get a budget and its linked transactions
        if budgets:
            sample_budget_pk = budgets[0]["Z_PK"]

            spent_query = """
                SELECT
                    b.Z_PK as budget_id,
                    b.ZAMOUNT1 as budget_amount,
                    SUM(ABS(t.ZAMOUNT1)) as spent_amount,
                    COUNT(t.Z_PK) as transaction_count
                FROM ZSYNCOBJECT b
                LEFT JOIN ZTRANSACTIONBUDGETLINK tbl ON tbl.ZBUDGET = b.Z_PK
                LEFT JOIN ZSYNCOBJECT t ON tbl.ZTRANSACTION = t.Z_PK
                WHERE b.Z_ENT = 44 AND b.Z_PK = ?
                GROUP BY b.Z_PK
            """
            spent_result = await db_manager.execute_query(
                spent_query, (sample_budget_pk,)
            )

            if spent_result:
                r = spent_result[0]
                logger.info(
                    f"  Budget {r['budget_id']}: Amount={r['budget_amount']}, Spent={r['spent_amount']}, Transactions={r['transaction_count']}"
                )

        # Phase 6: Find budget-account relationships
        logger.info("\n📊 Phase 6: Analyzing ZACCOUNTBUDGETLINK...")

        abl_query = "PRAGMA table_info(ZACCOUNTBUDGETLINK)"
        abl_cols = await db_manager.execute_query(abl_query)
        abl_col_names = [c["name"] for c in abl_cols]
        logger.info(f"ZACCOUNTBUDGETLINK columns: {abl_col_names}")

        account_link_query = """
            SELECT abl.*, a.ZNAME as account_name
            FROM ZACCOUNTBUDGETLINK abl
            LEFT JOIN ZSYNCOBJECT a ON abl.ZACCOUNT = a.Z_PK
            LIMIT 10
        """
        account_links = await db_manager.execute_query(account_link_query)

        logger.info(f"Found {len(account_links)} account-budget links")
        for al in account_links[:3]:
            logger.info(
                f"  Account {al.get('ZACCOUNT')} ({al.get('account_name')}) -> Budget {al.get('ZBUDGET')}"
            )

        # Phase 7: Check if there's a name field for budgets
        logger.info("\n📊 Phase 7: Looking for budget names/descriptions...")

        budget_fields_query = """
            SELECT ZNAME, ZNAME1, ZNAME2, ZDESCRIPTION, ZMEMO, ZCOMMENT
            FROM ZSYNCOBJECT
            WHERE Z_ENT = 44
            LIMIT 5
        """
        budget_fields = await db_manager.execute_query(budget_fields_query)

        for bf in budget_fields:
            non_null = {k: v for k, v in bf.items() if v is not None}
            logger.info(f"  Budget name fields: {non_null}")

        # Phase 8: Comprehensive budget view
        logger.info("\n📊 Phase 8: Building comprehensive budget view...")

        comprehensive_query = """
            SELECT
                b.Z_PK as budget_id,
                b.ZAMOUNT1 as budget_amount,
                b.ZBUDGETFROM,
                b.ZBUDGETTO,
                b.ZDATE1,
                b.ZCURRENCYEXCHANGERATE,
                cat_ref.ZNAME2 as from_category_name,
                (SELECT GROUP_CONCAT(so.ZNAME2, ', ')
                 FROM ZCATEGORYASSIGMENT ca
                 JOIN ZSYNCOBJECT so ON ca.ZCATEGORY = so.Z_PK
                 WHERE ca.ZBUDGET = b.Z_PK) as categories,
                (SELECT COUNT(*) FROM ZTRANSACTIONBUDGETLINK WHERE ZBUDGET = b.Z_PK) as transaction_count
            FROM ZSYNCOBJECT b
            LEFT JOIN ZSYNCOBJECT cat_ref ON b.ZBUDGETFROM = cat_ref.Z_PK
            WHERE b.Z_ENT = 44
            LIMIT 10
        """
        comprehensive = await db_manager.execute_query(comprehensive_query)

        logger.info("\nComprehensive Budget View:")
        logger.info("-" * 80)
        for row in comprehensive[:5]:
            logger.info(f"""
  Budget ID: {row["budget_id"]}
    Amount: {row["budget_amount"]}
    From Ref: {row["ZBUDGETFROM"]} ({row.get("from_category_name", "N/A")})
    To Ref: {row["ZBUDGETTO"]}
    Date: {row["ZDATE1"]}
    Categories: {row.get("categories", "None")}
    Transactions: {row["transaction_count"]}
""")

        # Phase 9: Check for currency information
        logger.info("\n📊 Phase 9: Currency information for budgets...")

        currency_query = """
            SELECT b.Z_PK, b.ZAMOUNT1, b.ZCURRENCYEXCHANGERATE,
                   c.ZCODE as currency_code
            FROM ZSYNCOBJECT b
            LEFT JOIN ZSYNCOBJECT c ON b.ZCURRENCY = c.Z_PK
            WHERE b.Z_ENT = 44
            LIMIT 5
        """
        currency_results = await db_manager.execute_query(currency_query)

        for cr in currency_results:
            logger.info(
                f"  Budget {cr['Z_PK']}: Amount={cr['ZAMOUNT1']}, Rate={cr['ZCURRENCYEXCHANGERATE']}, Currency={cr.get('currency_code', 'N/A')}"
            )

        # Phase 10: Summary
        logger.info("\n" + "=" * 70)
        logger.info("📋 SUMMARY: Budget Schema Understanding")
        logger.info("=" * 70)

        total_budgets = await db_manager.execute_query(
            "SELECT COUNT(*) as c FROM ZSYNCOBJECT WHERE Z_ENT = 44"
        )
        total_links = await db_manager.execute_query(
            "SELECT COUNT(*) as c FROM ZTRANSACTIONBUDGETLINK"
        )
        total_account_links = await db_manager.execute_query(
            "SELECT COUNT(*) as c FROM ZACCOUNTBUDGETLINK"
        )

        logger.info(f"""
Entity 44 = Budget
  - Total budgets: {total_budgets[0]["c"]}
  - Transaction links: {total_links[0]["c"]}
  - Account links: {total_account_links[0]["c"]}

Key Fields:
  - ZAMOUNT1: Budget limit amount
  - ZBUDGETFROM/ZBUDGETTO: Reference to period/category definitions
  - ZDATE1: Budget date (Core Data timestamp)
  - ZCURRENCYEXCHANGERATE: Currency conversion rate

Relationships:
  - ZCATEGORYASSIGMENT.ZBUDGET -> Links categories to budgets
  - ZTRANSACTIONBUDGETLINK.ZBUDGET -> Links transactions to budgets (for spent calculation)
  - ZACCOUNTBUDGETLINK.ZBUDGET -> Links accounts to budgets

Query Strategy:
  1. Get budgets from ZSYNCOBJECT WHERE Z_ENT = 44
  2. Get categories via ZCATEGORYASSIGMENT WHERE ZBUDGET = budget_id
  3. Calculate spent via ZTRANSACTIONBUDGETLINK join with transactions
""")

        logger.info("=" * 70)
        logger.info("✅ Deep investigation complete!")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Investigation failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(investigate_budgets_deep())
