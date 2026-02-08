#!/usr/bin/env python3
"""
Investigation script to discover budget-related entities in MoneyWiz database.
Looking for entities with budget fields like amounts, limits, categories, periods.
"""

import asyncio
from collections import defaultdict
import logging
from pathlib import Path

from src.moneywiz_mcp_server.config import Config
from src.moneywiz_mcp_server.database.connection import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def investigate_budgets():
    """Find budget-related entities in MoneyWiz database."""

    # Load configuration
    config = Config.from_env()

    # Initialize database manager
    db_manager = DatabaseManager(config.database_path, read_only=True)
    await db_manager.initialize()

    try:
        logger.info("=" * 70)
        logger.info("🎯 MoneyWiz Budget Schema Investigation")
        logger.info("=" * 70)

        # Phase 1: Look for dedicated budget tables
        logger.info("\n📋 Phase 1: Searching for budget-related tables...")

        tables_query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        tables = await db_manager.execute_query(tables_query)

        budget_keywords = ["budget", "goal", "limit", "allocation", "plan", "target"]
        budget_tables = []

        for table in tables:
            table_name = table["name"]
            if any(keyword in table_name.lower() for keyword in budget_keywords):
                budget_tables.append(table_name)

        if budget_tables:
            logger.info(
                f"Found {len(budget_tables)} potentially budget-related tables:"
            )
            for table_name in budget_tables:
                await analyze_table(db_manager, table_name)
        else:
            logger.info(
                "No dedicated budget tables found. Checking ZSYNCOBJECT entities..."
            )

        # Phase 2: Get all entity types and their counts
        logger.info("\n📊 Phase 2: Analyzing all entity types...")

        entity_query = """
            SELECT Z_ENT, COUNT(*) as count
            FROM ZSYNCOBJECT
            GROUP BY Z_ENT
            ORDER BY Z_ENT
        """
        entity_results = await db_manager.execute_query(entity_query)

        # Known entities from existing implementation
        known_entities = {
            10: "BankChequeAccount",
            11: "BankSavingAccount",
            12: "CashAccount",
            13: "CreditCardAccount",
            14: "LoanAccount",
            15: "InvestmentAccount",
            16: "ForexAccount",
            19: "Category",
            28: "Payee",
            33: "ScheduledTransfer",
            34: "ScheduledTransaction",
            35: "Tag",
            37: "DepositTransaction",
            38: "InvestmentExchange",
            40: "InvestmentBuy",
            41: "InvestmentSell",
            42: "Reconcile",
            43: "Refund",
            44: "Budget (suspected)",
            45: "TransferDeposit",
            46: "TransferWithdraw",
            47: "WithdrawTransaction",
        }

        logger.info("\nEntity Type Summary:")
        logger.info("-" * 50)

        unknown_entities = []
        for row in entity_results:
            ent_type = row["Z_ENT"]
            count = row["count"]
            name = known_entities.get(ent_type, "UNKNOWN")
            marker = "📌" if name == "UNKNOWN" else "✓"
            logger.info(f"{marker} Entity {ent_type:3d}: {count:5d} records - {name}")

            if name == "UNKNOWN":
                unknown_entities.append(ent_type)

        # Phase 3: Search for budget-related fields in entities
        logger.info("\n🔍 Phase 3: Searching for budget-related fields...")

        budget_field_patterns = [
            "BUDGET",
            "LIMIT",
            "GOAL",
            "TARGET",
            "ALLOWANCE",
            "ALLOCATION",
            "PLANNED",
            "ZMAX",
            "ZMIN",
        ]

        period_field_patterns = [
            "PERIOD",
            "MONTH",
            "YEAR",
            "START",
            "END",
            "FROM",
            "TO",
            "DURATION",
        ]

        # Check all entity types for budget-like fields
        candidates = []

        for row in entity_results:
            ent_type = row["Z_ENT"]
            count = row["count"]

            # Get sample record
            sample_query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? LIMIT 1"
            samples = await db_manager.execute_query(sample_query, (ent_type,))

            if not samples:
                continue

            sample = samples[0]
            field_names = list(sample.keys())

            # Count budget-related fields
            budget_fields = []
            period_fields = []
            category_fields = []
            amount_fields = []

            for field_name in field_names:
                upper_field = field_name.upper()

                # Budget-related fields
                if any(pattern in upper_field for pattern in budget_field_patterns):
                    budget_fields.append(field_name)

                # Period-related fields
                if any(pattern in upper_field for pattern in period_field_patterns):
                    period_fields.append(field_name)

                # Category links
                if "CATEGORY" in upper_field or "ZCATEGORY" in upper_field:
                    category_fields.append(field_name)

                # Amount fields
                if "AMOUNT" in upper_field or "VALUE" in upper_field:
                    amount_fields.append(field_name)

            # Score this entity for budget likelihood
            score = 0
            score += len(budget_fields) * 3  # Budget fields are strong indicators
            score += len(period_fields) * 1  # Period fields are weak indicators
            score += len(category_fields) * 2  # Category links are moderate indicators
            score += len(amount_fields) * 1  # Amount fields are weak indicators

            if score >= 3:  # Threshold for candidate
                candidates.append(
                    {
                        "entity_type": ent_type,
                        "count": count,
                        "score": score,
                        "budget_fields": budget_fields,
                        "period_fields": period_fields,
                        "category_fields": category_fields,
                        "amount_fields": amount_fields,
                        "known_name": known_entities.get(ent_type, "UNKNOWN"),
                    }
                )

        # Sort candidates by score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        if candidates:
            logger.info(f"\n🎯 Found {len(candidates)} budget candidate entities:")
            for candidate in candidates[:10]:  # Top 10
                logger.info(
                    f"\n📊 Entity {candidate['entity_type']} (score: {candidate['score']})"
                )
                logger.info(f"   Known as: {candidate['known_name']}")
                logger.info(f"   Record count: {candidate['count']}")
                if candidate["budget_fields"]:
                    logger.info(f"   Budget fields: {candidate['budget_fields']}")
                if candidate["period_fields"]:
                    logger.info(f"   Period fields: {candidate['period_fields'][:5]}")
                if candidate["category_fields"]:
                    logger.info(f"   Category fields: {candidate['category_fields']}")
                if candidate["amount_fields"]:
                    logger.info(f"   Amount fields: {candidate['amount_fields'][:5]}")

        # Phase 4: Deep dive into top candidates
        logger.info("\n🔬 Phase 4: Deep analysis of top candidates...")

        for candidate in candidates[:5]:
            await analyze_entity_deep(db_manager, candidate["entity_type"])

        # Phase 5: Check entity 44 specifically (suspected budget entity)
        logger.info("\n🎯 Phase 5: Special analysis of Entity 44 (suspected budget)...")
        await analyze_entity_deep(db_manager, 44)

        # Phase 6: Look for any table with "budget" in field names
        logger.info("\n🔍 Phase 6: Scanning all tables for budget-related columns...")
        await scan_all_tables_for_budget_fields(db_manager)

        logger.info("\n" + "=" * 70)
        logger.info("✅ Investigation complete!")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Investigation failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await db_manager.close()


async def analyze_table(db_manager: DatabaseManager, table_name: str):
    """Analyze a specific table's structure and data."""
    logger.info(f"\n  📋 Table: {table_name}")

    try:
        # Get table structure
        pragma_query = f"PRAGMA table_info({table_name})"
        columns = await db_manager.execute_query(pragma_query)
        column_names = [col["name"] for col in columns]
        logger.info(f"     Columns ({len(column_names)}): {column_names[:10]}...")

        # Get record count
        count_query = f"SELECT COUNT(*) as count FROM {table_name}"
        count_result = await db_manager.execute_query(count_query)
        count = count_result[0]["count"] if count_result else 0
        logger.info(f"     Records: {count}")

        # Get sample data
        if count > 0:
            sample_query = f"SELECT * FROM {table_name} LIMIT 3"
            samples = await db_manager.execute_query(sample_query)
            if samples:
                logger.info("     Sample data:")
                for i, sample in enumerate(samples[:2]):
                    non_null = {k: v for k, v in sample.items() if v is not None}
                    logger.info(
                        f"       Row {i + 1}: {dict(list(non_null.items())[:5])}"
                    )

    except Exception as e:
        logger.info(f"     Error: {e}")


async def analyze_entity_deep(db_manager: DatabaseManager, entity_type: int):
    """Deep analysis of a specific entity type."""
    logger.info(f"\n  🔬 Deep analysis of Entity {entity_type}:")

    try:
        # Get all records for this entity
        query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ?"
        records = await db_manager.execute_query(query, (entity_type,))

        if not records:
            logger.info("     No records found")
            return

        logger.info(f"     Total records: {len(records)}")

        # Analyze field values
        sample = records[0]
        field_stats = {}

        for field_name in sample:
            # Count non-null values
            non_null_count = sum(1 for r in records if r.get(field_name) is not None)

            # Get unique values (for fields with few unique values)
            unique_values = {
                r.get(field_name) for r in records if r.get(field_name) is not None
            }

            if non_null_count > 0:
                field_stats[field_name] = {
                    "non_null_count": non_null_count,
                    "unique_count": len(unique_values),
                    "sample_values": list(unique_values)[:3],
                }

        # Show interesting fields (fields with data)
        interesting_fields = [
            (name, stats)
            for name, stats in field_stats.items()
            if stats["non_null_count"] > 0 and not name.startswith("Z_")
        ]

        # Sort by relevance (budget-related first)
        budget_keywords = [
            "budget",
            "limit",
            "goal",
            "amount",
            "category",
            "period",
            "month",
            "year",
        ]

        def relevance_score(item):
            name = item[0].lower()
            return (
                sum(1 for kw in budget_keywords if kw in name) * 100
                + item[1]["non_null_count"]
            )

        interesting_fields.sort(key=relevance_score, reverse=True)

        logger.info("     Fields with data (sorted by relevance):")
        for field_name, stats in interesting_fields[:15]:
            sample_str = str(stats["sample_values"])[:50]
            logger.info(
                f"       {field_name}: {stats['non_null_count']}/{len(records)} records, "
                f"{stats['unique_count']} unique, samples: {sample_str}"
            )

    except Exception as e:
        logger.info(f"     Error: {e}")


async def scan_all_tables_for_budget_fields(db_manager: DatabaseManager):
    """Scan all tables for fields containing 'budget'."""
    try:
        tables_query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        tables = await db_manager.execute_query(tables_query)

        budget_matches = []

        for table in tables:
            table_name = table["name"]

            try:
                pragma_query = f"PRAGMA table_info({table_name})"
                columns = await db_manager.execute_query(pragma_query)

                for col in columns:
                    col_name = col["name"]
                    if "budget" in col_name.lower():
                        budget_matches.append(
                            {
                                "table": table_name,
                                "column": col_name,
                                "type": col["type"],
                            }
                        )

            except Exception:
                pass

        if budget_matches:
            logger.info(
                f"\n  Found {len(budget_matches)} columns with 'budget' in name:"
            )
            for match in budget_matches:
                logger.info(f"    {match['table']}.{match['column']} ({match['type']})")

                # Get sample values
                try:
                    sample_query = f"SELECT {match['column']} FROM {match['table']} WHERE {match['column']} IS NOT NULL LIMIT 5"
                    samples = await db_manager.execute_query(sample_query)
                    if samples:
                        values = [s[match["column"]] for s in samples]
                        logger.info(f"      Sample values: {values}")
                except Exception:
                    pass
        else:
            logger.info("  No columns with 'budget' in name found")

    except Exception as e:
        logger.info(f"  Error scanning tables: {e}")


if __name__ == "__main__":
    asyncio.run(investigate_budgets())
