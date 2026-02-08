#!/usr/bin/env python3
"""
Focused investigation script to find actual scheduled transaction entities.
Looking for entities with transaction-like fields (amounts, accounts, etc.).
"""

import asyncio
import logging
from pathlib import Path

from src.moneywiz_mcp_server.config import Config
from src.moneywiz_mcp_server.database.connection import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def find_scheduled_transaction_entities():
    """Find entities that look like actual scheduled transactions."""

    # Load configuration
    config = Config.from_env()

    # Initialize database manager
    db_manager = DatabaseManager(config.database_path, read_only=True)
    await db_manager.initialize()

    try:
        logger.info("🎯 Searching for actual scheduled transaction entities...")

        # Get all entity types
        entity_query = "SELECT DISTINCT Z_ENT FROM ZSYNCOBJECT ORDER BY Z_ENT"
        entity_results = await db_manager.execute_query(entity_query)

        # Known transaction-like entities to exclude
        known_entities = {10, 11, 12, 13, 14, 15, 16, 19, 28, 37, 45, 46, 47}
        unknown_entities = [
            r["Z_ENT"] for r in entity_results if r["Z_ENT"] not in known_entities
        ]

        logger.info(f"Investigating {len(unknown_entities)} unknown entities...")

        potential_scheduled_entities = []

        for ent_type in unknown_entities:
            logger.info(f"\n🔍 Analyzing Entity Type {ent_type}")

            # Get sample records
            sample_query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? LIMIT 3"
            samples = await db_manager.execute_query(sample_query, (ent_type,))

            if not samples:
                continue

            sample = samples[0]

            # Check for transaction-like characteristics
            has_amount = any("amount" in field.lower() for field in sample)
            has_account = any("account" in field.lower() for field in sample)
            has_date = any("date" in field.lower() for field in sample)
            has_schedule_fields = any(
                keyword in field.lower()
                for field in sample
                for keyword in ["repeat", "next", "interval", "occur"]
            )

            # Score this entity based on transaction-like characteristics
            score = 0
            if has_amount:
                score += 3
            if has_account:
                score += 3
            if has_date:
                score += 2
            if has_schedule_fields:
                score += 2

            # Look for specific interesting fields
            transaction_fields = []
            for field_name, value in sample.items():
                if any(
                    keyword in field_name.lower()
                    for keyword in [
                        "amount",
                        "account",
                        "category",
                        "payee",
                        "description",
                        "memo",
                    ]
                ):
                    transaction_fields.append((field_name, value))

            schedule_fields = []
            for field_name, value in sample.items():
                if any(
                    keyword in field_name.lower()
                    for keyword in [
                        "repeat",
                        "next",
                        "interval",
                        "occur",
                        "end",
                        "frequency",
                    ]
                ):
                    schedule_fields.append((field_name, value))

            logger.info(f"  Score: {score}/10")
            logger.info(f"  Records: {len(samples)}")

            if transaction_fields:
                logger.info(
                    f"  💰 Transaction fields: {[f[0] for f in transaction_fields[:5]]}"
                )

            if schedule_fields:
                logger.info(
                    f"  📅 Schedule fields: {[f[0] for f in schedule_fields[:5]]}"
                )

            # Consider it a potential scheduled transaction entity if score >= 6
            if score >= 6:
                potential_scheduled_entities.append(
                    {
                        "entity_type": ent_type,
                        "score": score,
                        "record_count": len(samples),
                        "transaction_fields": transaction_fields,
                        "schedule_fields": schedule_fields,
                        "sample_record": sample,
                    }
                )
                logger.info("  ⭐ POTENTIAL SCHEDULED TRANSACTION ENTITY!")

        # Report findings
        logger.info(
            f"\n🎉 Found {len(potential_scheduled_entities)} potential scheduled transaction entities:"
        )

        for entity in sorted(
            potential_scheduled_entities, key=lambda x: x["score"], reverse=True
        ):
            logger.info(
                f"\n📊 Entity Type {entity['entity_type']} (Score: {entity['score']}/10)"
            )
            logger.info(f"   Records: {entity['record_count']}")

            # Show key transaction fields
            if entity["transaction_fields"]:
                logger.info("   💰 Key Transaction Fields:")
                for field_name, value in entity["transaction_fields"][:5]:
                    if value is not None:
                        logger.info(f"      {field_name}: {value}")

            # Show key schedule fields
            if entity["schedule_fields"]:
                logger.info("   📅 Key Schedule Fields:")
                for field_name, value in entity["schedule_fields"][:5]:
                    if value is not None:
                        logger.info(f"      {field_name}: {value}")

        # If we found candidates, investigate their structure more deeply
        if potential_scheduled_entities:
            best_candidate = potential_scheduled_entities[0]
            logger.info(
                f"\n🔬 Deep analysis of best candidate: Entity {best_candidate['entity_type']}"
            )

            # Get more samples from the best candidate
            deep_query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? LIMIT 10"
            deep_samples = await db_manager.execute_query(
                deep_query, (best_candidate["entity_type"],)
            )

            logger.info(f"Analyzing {len(deep_samples)} records...")

            # Look for patterns in the data
            field_analysis = {}
            for sample in deep_samples:
                for field_name, value in sample.items():
                    if field_name not in field_analysis:
                        field_analysis[field_name] = {"values": [], "non_null_count": 0}

                    field_analysis[field_name]["values"].append(value)
                    if value is not None:
                        field_analysis[field_name]["non_null_count"] += 1

            # Report on fields that are commonly populated
            logger.info("\n📈 Field analysis (fields with data in most records):")
            for field_name, analysis in field_analysis.items():
                if (
                    analysis["non_null_count"] >= len(deep_samples) * 0.5
                ):  # 50% or more records have data
                    unique_values = {
                        str(v) for v in analysis["values"] if v is not None
                    }
                    logger.info(
                        f"   {field_name}: {analysis['non_null_count']}/{len(deep_samples)} records, {len(unique_values)} unique values"
                    )

                    # Show sample values for key fields
                    if any(
                        keyword in field_name.lower()
                        for keyword in ["amount", "date", "account", "next", "end"]
                    ):
                        sample_values = list(unique_values)[:3]
                        logger.info(f"      Sample values: {sample_values}")

        logger.info("\n✅ Focused investigation complete!")

    except Exception as e:
        logger.error(f"Investigation failed: {e}")

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(find_scheduled_transaction_entities())
