#!/usr/bin/env python3
"""
Investigation script to explore MoneyWiz database schema for scheduled transactions.
This script will help us understand how scheduled/recurring transactions are stored.
"""

import asyncio
import logging
from pathlib import Path

from src.moneywiz_mcp_server.config import Config
from src.moneywiz_mcp_server.database.connection import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def investigate_scheduled_transactions():
    """Investigate the MoneyWiz database to find scheduled transaction entities."""

    # Load configuration
    config = Config.from_env()

    # Validate database exists
    if not Path(config.database_path).exists():
        logger.error(f"Database not found at: {config.database_path}")
        return

    # Initialize database manager
    db_manager = DatabaseManager(config.database_path, read_only=True)
    await db_manager.initialize()

    try:
        logger.info("🔍 Starting scheduled transaction investigation...")

        # 1. Find all entity types in the database
        logger.info("\n📊 Step 1: Discovering all entity types...")
        entity_query = "SELECT DISTINCT Z_ENT FROM ZSYNCOBJECT ORDER BY Z_ENT"
        entity_results = await db_manager.execute_query(entity_query)

        logger.info(f"Found {len(entity_results)} entity types:")
        known_entities = {
            10: "Account (Checking)",
            11: "Account (Savings)",
            12: "Account (Credit Card)",
            13: "Account (Investment)",
            14: "Account (Cash)",
            15: "Account (Loan)",
            16: "Account (Other)",
            19: "Category",
            28: "Payee",
            37: "Transaction (Deposit)",
            45: "Transaction (Transfer Out)",
            46: "Transaction (Transfer In)",
            47: "Transaction (Withdraw)",
        }

        unknown_entities = []
        for result in entity_results:
            ent_type = result["Z_ENT"]
            if ent_type in known_entities:
                logger.info(f"  {ent_type}: {known_entities[ent_type]}")
            else:
                unknown_entities.append(ent_type)
                logger.info(
                    f"  {ent_type}: UNKNOWN - potential scheduled transaction entity"
                )

        # 2. Investigate unknown entities that might be scheduled transactions
        logger.info(
            f"\n🔍 Step 2: Investigating {len(unknown_entities)} unknown entities..."
        )

        for ent_type in unknown_entities:
            logger.info(f"\n--- Investigating Entity Type {ent_type} ---")

            # Get sample records for this entity type
            sample_query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? LIMIT 5"
            samples = await db_manager.execute_query(sample_query, (ent_type,))

            if not samples:
                logger.info(f"  No records found for entity {ent_type}")
                continue

            logger.info(f"  Found {len(samples)} sample records")

            # Analyze field patterns that might indicate scheduled transactions
            sample = samples[0]
            potential_schedule_fields = []

            for field_name, value in sample.items():
                if any(
                    keyword in field_name.lower()
                    for keyword in [
                        "repeat",
                        "recur",
                        "schedule",
                        "next",
                        "end",
                        "occur",
                        "interval",
                        "frequency",
                    ]
                ):
                    potential_schedule_fields.append((field_name, value))

            if potential_schedule_fields:
                logger.info("  🎯 Potential scheduled transaction fields found:")
                for field_name, value in potential_schedule_fields:
                    logger.info(f"    {field_name}: {value}")
            else:
                logger.info("  No obvious scheduling fields found")

            # Look for date fields that might indicate scheduling
            date_fields = []
            for field_name, value in sample.items():
                if "date" in field_name.lower() or "time" in field_name.lower():
                    date_fields.append((field_name, value))

            if date_fields:
                logger.info("  📅 Date fields found:")
                for field_name, value in date_fields[:3]:  # Show first 3 date fields
                    logger.info(f"    {field_name}: {value}")

        # 3. Look for tables that might contain scheduled transaction relationships
        logger.info(
            "\n🔗 Step 3: Looking for scheduled transaction relationship tables..."
        )

        # Get all table names
        tables_query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        tables = await db_manager.execute_query(tables_query)

        schedule_related_tables = []
        for table in tables:
            table_name = table["name"]
            if any(
                keyword in table_name.lower()
                for keyword in ["schedule", "recur", "repeat", "template", "plan"]
            ):
                schedule_related_tables.append(table_name)

        if schedule_related_tables:
            logger.info(
                f"Found {len(schedule_related_tables)} potentially relevant tables:"
            )
            for table_name in schedule_related_tables:
                logger.info(f"  📋 {table_name}")

                # Get sample data from each table
                sample_query = f"SELECT * FROM {table_name} LIMIT 3"
                try:
                    samples = await db_manager.execute_query(sample_query)
                    if samples:
                        logger.info(f"    Sample fields: {list(samples[0].keys())}")
                except Exception as e:
                    logger.info(f"    Error querying table: {e}")
        else:
            logger.info("No obviously schedule-related tables found")

        # 4. Search for specific field patterns in ZSYNCOBJECT
        logger.info("\n🔍 Step 4: Searching for scheduling-related field patterns...")

        # Get all column names from ZSYNCOBJECT
        pragma_query = "PRAGMA table_info(ZSYNCOBJECT)"
        columns = await db_manager.execute_query(pragma_query)

        scheduling_columns = []
        for col in columns:
            col_name = col["name"]
            if any(
                keyword in col_name.lower()
                for keyword in [
                    "repeat",
                    "recur",
                    "schedule",
                    "next",
                    "end",
                    "occur",
                    "interval",
                    "frequency",
                    "template",
                    "plan",
                    "auto",
                ]
            ):
                scheduling_columns.append(col_name)

        if scheduling_columns:
            logger.info(
                f"Found {len(scheduling_columns)} potentially scheduling-related columns:"
            )
            for col_name in scheduling_columns:
                logger.info(f"  📊 {col_name}")

        logger.info("\n✅ Investigation complete!")
        logger.info("\nNext steps:")
        logger.info(
            "1. Analyze the unknown entity types to identify scheduled transactions"
        )
        logger.info("2. Examine the scheduling-related fields for occurrence tracking")
        logger.info(
            "3. Look for relationships between scheduled transactions and regular transactions"
        )

    except Exception as e:
        logger.error(f"Investigation failed: {e}")

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(investigate_scheduled_transactions())
