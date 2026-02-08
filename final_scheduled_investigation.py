#!/usr/bin/env python3
"""
Final targeted investigation to find actual scheduled transaction entities.
Looking for entities with real transaction fields like amounts, dates, accounts.
"""

import asyncio
import logging
from pathlib import Path

from src.moneywiz_mcp_server.config import Config
from src.moneywiz_mcp_server.database.connection import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def find_real_scheduled_transactions():
    """Find entities that are actual scheduled transactions, not settings."""

    # Load configuration
    config = Config.from_env()

    # Initialize database manager
    db_manager = DatabaseManager(config.database_path, read_only=True)
    await db_manager.initialize()

    try:
        logger.info("🎯 Final search for actual scheduled transaction entities...")

        # Get all entity types except known ones
        entity_query = "SELECT DISTINCT Z_ENT FROM ZSYNCOBJECT ORDER BY Z_ENT"
        entity_results = await db_manager.execute_query(entity_query)

        # Known entities to exclude
        known_entities = {10, 11, 12, 13, 14, 15, 16, 19, 28, 37, 45, 46, 47}
        unknown_entities = [
            r["Z_ENT"] for r in entity_results if r["Z_ENT"] not in known_entities
        ]

        logger.info(f"Investigating {len(unknown_entities)} unknown entities...")

        # Look for transaction-like field patterns that match real transactions
        transaction_field_patterns = [
            "ZAMOUNT",  # Transaction amount (like regular transactions)
            "ZDATE",  # Transaction date
            "ZDESCRIPTION",  # Transaction description
            "ZMEMO",  # Transaction memo
            "ZACCOUNT",  # Link to account
            "ZCATEGORY",  # Link to category
            "ZPAYEE",  # Link to payee
        ]

        # Look for scheduling field patterns
        scheduling_field_patterns = [
            "ZNEXT",  # Next execution date
            "ZINTERVAL",  # Repeat interval
            "ZREPEAT",  # Repeat information
            "ZFREQUENCY",  # Frequency
            "ZOCCUR",  # Occurrence count
            "ZEND",  # End date/condition
        ]

        candidates = []

        for ent_type in unknown_entities:
            # Get sample records
            sample_query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? LIMIT 5"
            samples = await db_manager.execute_query(sample_query, (ent_type,))

            if not samples:
                continue

            sample = samples[0]
            field_names = list(sample.keys())

            # Count actual transaction-like fields (must match exact patterns)
            transaction_field_count = 0
            found_transaction_fields = []

            for field_name in field_names:
                for pattern in transaction_field_patterns:
                    if pattern in field_name and field_name.startswith("Z"):
                        transaction_field_count += 1
                        found_transaction_fields.append(field_name)
                        break

            # Count scheduling fields
            scheduling_field_count = 0
            found_scheduling_fields = []

            for field_name in field_names:
                for pattern in scheduling_field_patterns:
                    if pattern in field_name and field_name.startswith("Z"):
                        scheduling_field_count += 1
                        found_scheduling_fields.append(field_name)
                        break

            # Must have at least 2 transaction fields and 1 scheduling field
            if transaction_field_count >= 2 and scheduling_field_count >= 1:
                # Check if records have actual data (not all null)
                non_null_count = sum(
                    1 for value in sample.values() if value is not None
                )
                total_fields = len(sample)
                data_ratio = non_null_count / total_fields if total_fields > 0 else 0

                candidates.append(
                    {
                        "entity_type": ent_type,
                        "record_count": len(samples),
                        "transaction_fields": found_transaction_fields,
                        "scheduling_fields": found_scheduling_fields,
                        "data_ratio": data_ratio,
                        "sample_record": sample,
                    }
                )

                logger.info(f"🎯 CANDIDATE: Entity {ent_type}")
                logger.info(f"   Records: {len(samples)}")
                logger.info(f"   Transaction fields: {found_transaction_fields}")
                logger.info(f"   Scheduling fields: {found_scheduling_fields}")
                logger.info(f"   Data completeness: {data_ratio:.1%}")

        # If no candidates found with strict criteria, relax and look for any entity
        # with scheduling-related words that has transaction-like data
        if not candidates:
            logger.info("\n🔍 No strict candidates found. Broadening search...")

            for ent_type in unknown_entities:
                sample_query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? LIMIT 3"
                samples = await db_manager.execute_query(sample_query, (ent_type,))

                if not samples:
                    continue

                sample = samples[0]

                # Look for any scheduling-related fields
                has_scheduling_hints = any(
                    keyword in field_name.lower()
                    for field_name in sample
                    for keyword in [
                        "repeat",
                        "next",
                        "schedule",
                        "recur",
                        "interval",
                        "freq",
                    ]
                )

                # Look for amount-like fields with actual numeric values
                has_amount_data = False
                for field_name, value in sample.items():
                    if (
                        "amount" in field_name.lower()
                        and isinstance(value, int | float)
                        and value != 0
                    ):
                        has_amount_data = True
                        break

                if has_scheduling_hints and has_amount_data:
                    logger.info(
                        f"🤔 POSSIBLE: Entity {ent_type} - has scheduling hints + amount data"
                    )
                    logger.info(f"   Records: {len(samples)}")

                    # Show relevant fields
                    relevant_fields = []
                    for field_name, value in sample.items():
                        if any(
                            keyword in field_name.lower()
                            for keyword in [
                                "amount",
                                "date",
                                "account",
                                "category",
                                "payee",
                                "description",
                                "repeat",
                                "next",
                                "schedule",
                                "recur",
                                "interval",
                                "freq",
                                "end",
                            ]
                        ):
                            relevant_fields.append((field_name, value))

                    logger.info("   Relevant fields:")
                    for field_name, value in relevant_fields[:10]:
                        logger.info(f"     {field_name}: {value}")

        # Alternative approach: Look at other Core Data tables
        logger.info("\n🔍 Checking for dedicated scheduled transaction tables...")

        tables_query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        tables = await db_manager.execute_query(tables_query)

        schedule_tables = []
        for table in tables:
            table_name = table["name"]
            if any(
                keyword in table_name.lower()
                for keyword in [
                    "schedule",
                    "recur",
                    "repeat",
                    "template",
                    "planned",
                    "future",
                ]
            ):
                schedule_tables.append(table_name)

        if schedule_tables:
            logger.info(f"Found {len(schedule_tables)} potentially relevant tables:")
            for table_name in schedule_tables:
                logger.info(f"📋 {table_name}")

                try:
                    # Get table structure
                    pragma_query = f"PRAGMA table_info({table_name})"
                    columns = await db_manager.execute_query(pragma_query)
                    column_names = [col["name"] for col in columns]
                    logger.info(f"   Columns: {column_names}")

                    # Get sample data
                    sample_query = f"SELECT * FROM {table_name} LIMIT 3"
                    samples = await db_manager.execute_query(sample_query)
                    logger.info(f"   Records: {len(samples)}")

                    if samples:
                        # Show interesting fields
                        sample = samples[0]
                        interesting_fields = []
                        for field_name, value in sample.items():
                            if value is not None and any(
                                keyword in field_name.lower()
                                for keyword in [
                                    "amount",
                                    "date",
                                    "next",
                                    "repeat",
                                    "end",
                                    "occur",
                                ]
                            ):
                                interesting_fields.append((field_name, value))

                        if interesting_fields:
                            logger.info("   Key fields:")
                            for field_name, value in interesting_fields[:5]:
                                logger.info(f"     {field_name}: {value}")

                except Exception as e:
                    logger.info(f"   Error querying table: {e}")

        if candidates:
            logger.info(
                f"\n🎉 Found {len(candidates)} strong candidates for scheduled transactions!"
            )
            for candidate in candidates:
                logger.info(f"📊 Entity {candidate['entity_type']}:")
                logger.info(f"   Transaction fields: {candidate['transaction_fields']}")
                logger.info(f"   Scheduling fields: {candidate['scheduling_fields']}")
        else:
            logger.info("\n❌ No clear scheduled transaction entities found.")
            logger.info("This might mean:")
            logger.info("1. MoneyWiz stores scheduled transactions differently")
            logger.info("2. No scheduled transactions exist in this database")
            logger.info("3. They're stored in a separate table or format")

        logger.info("\n✅ Final investigation complete!")

    except Exception as e:
        logger.error(f"Investigation failed: {e}")

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(find_real_scheduled_transactions())
