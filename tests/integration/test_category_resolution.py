"""Integration tests for category resolution - Debug uncategorized transactions issue."""


import pytest

from moneywiz_mcp_server.config import Config
from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.services.transaction_service import TransactionService


class TestCategoryResolution:
    """Test suite to debug category resolution issues."""

    @pytest.fixture
    async def real_db_manager(self):
        """Create a real database manager for integration testing."""
        try:
            config = Config.from_env()
            db_manager = DatabaseManager(config.database_path, read_only=True)
            await db_manager.initialize()
            yield db_manager
        except Exception as e:
            pytest.skip(f"Cannot connect to real database: {e}")
        finally:
            if "db_manager" in locals():
                await db_manager.close()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_category_assignment_table_exists(self, real_db_manager):
        """Test that ZCATEGORYASSIGMENT table exists and has data."""
        # Check if table exists
        table_check_query = """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='ZCATEGORYASSIGMENT'
        """

        result = await real_db_manager.execute_query(table_check_query)
        assert len(result) > 0, "ZCATEGORYASSIGMENT table does not exist"

        # Check if table has data
        count_query = "SELECT COUNT(*) as count FROM ZCATEGORYASSIGMENT"
        count_result = await real_db_manager.execute_query(count_query)
        assert count_result[0]["count"] > 0, "ZCATEGORYASSIGMENT table is empty"

        print(f"✅ ZCATEGORYASSIGMENT table has {count_result[0]['count']} records")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_category_assignment_structure(self, real_db_manager):
        """Test the structure of ZCATEGORYASSIGMENT table."""
        # Get table schema
        schema_query = "PRAGMA table_info(ZCATEGORYASSIGMENT)"
        schema = await real_db_manager.execute_query(schema_query)

        column_names = [col["name"] for col in schema]
        print(f"ZCATEGORYASSIGMENT columns: {column_names}")

        # Check required columns exist
        assert "ZTRANSACTION" in column_names, "Missing ZTRANSACTION column"
        assert "ZCATEGORY" in column_names, "Missing ZCATEGORY column"

        # Sample some data
        sample_query = "SELECT * FROM ZCATEGORYASSIGMENT LIMIT 5"
        samples = await real_db_manager.execute_query(sample_query)

        print("Sample ZCATEGORYASSIGMENT data:")
        for sample in samples[:3]:
            print(
                f"  Transaction: {sample.get('ZTRANSACTION')}, Category: {sample.get('ZCATEGORY')}"
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_category_names_table(self, real_db_manager):
        """Test category names in ZSYNCOBJECT table."""
        # Get categories from ZSYNCOBJECT where Z_ENT = 19
        category_query = """
        SELECT Z_PK, ZNAME, ZNAME2
        FROM ZSYNCOBJECT
        WHERE Z_ENT = 19
        LIMIT 10
        """

        categories = await real_db_manager.execute_query(category_query)
        assert len(categories) > 0, "No categories found in ZSYNCOBJECT with Z_ENT = 19"

        print("Sample categories:")
        for cat in categories[:5]:
            print(
                f"  ID: {cat.get('Z_PK')}, ZNAME: {cat.get('ZNAME')}, ZNAME2: {cat.get('ZNAME2')}"
            )

        # Check which field has the actual category names
        zname_with_values = [cat for cat in categories if cat.get("ZNAME")]
        zname2_with_values = [cat for cat in categories if cat.get("ZNAME2")]

        print(f"Categories with ZNAME: {len(zname_with_values)}")
        print(f"Categories with ZNAME2: {len(zname2_with_values)}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_transaction_category_join(self, real_db_manager):
        """Test joining transactions with their categories."""
        # Get some transactions with categories
        join_query = """
        SELECT
            t.Z_PK as transaction_id,
            t.ZDESCRIPTION as description,
            ca.ZCATEGORY as category_id,
            c.ZNAME as category_name,
            c.ZNAME2 as category_name2
        FROM ZSYNCOBJECT t
        LEFT JOIN ZCATEGORYASSIGMENT ca ON ca.ZTRANSACTION = t.Z_PK
        LEFT JOIN ZSYNCOBJECT c ON c.Z_PK = ca.ZCATEGORY AND c.Z_ENT = 19
        WHERE t.Z_ENT IN (37, 45, 46, 47)
        AND t.ZDESCRIPTION IS NOT NULL
        LIMIT 20
        """

        results = await real_db_manager.execute_query(join_query)
        assert len(results) > 0, "No transactions found"

        categorized_count = 0
        uncategorized_count = 0

        print("Sample transaction-category joins:")
        for result in results[:10]:
            category_name = result.get("category_name2") or result.get("category_name")
            if category_name:
                categorized_count += 1
                print(f"  ✅ {result.get('description')[:30]:<30} → {category_name}")
            else:
                uncategorized_count += 1
                print(f"  ❌ {result.get('description')[:30]:<30} → UNCATEGORIZED")

        print(
            f"\nCategorized: {categorized_count}, Uncategorized: {uncategorized_count}"
        )

        if uncategorized_count > categorized_count:
            print("⚠️  WARNING: Most transactions appear uncategorized!")

            # Debug: Check if category assignments exist but names are missing
            debug_query = """
            SELECT
                COUNT(*) as total_assignments,
                COUNT(c.ZNAME) as with_zname,
                COUNT(c.ZNAME2) as with_zname2
            FROM ZCATEGORYASSIGMENT ca
            LEFT JOIN ZSYNCOBJECT c ON c.Z_PK = ca.ZCATEGORY AND c.Z_ENT = 19
            """
            debug_result = await real_db_manager.execute_query(debug_query)
            print(f"Debug - Total assignments: {debug_result[0]['total_assignments']}")
            print(f"Debug - With ZNAME: {debug_result[0]['with_zname']}")
            print(f"Debug - With ZNAME2: {debug_result[0]['with_zname2']}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_transaction_service_category_resolution(self, real_db_manager):
        """Test actual TransactionService category resolution."""
        # Create transaction service
        transaction_service = TransactionService(real_db_manager)

        # Get some real transactions
        raw_query = """
        SELECT Z_PK, Z_ENT, ZACCOUNT2, ZAMOUNT1, ZDATEADDED, ZDESCRIPTION, ZPAYEE
        FROM ZSYNCOBJECT
        WHERE Z_ENT IN (37, 45, 46, 47)
        AND ZDESCRIPTION IS NOT NULL
        LIMIT 10
        """

        raw_transactions = await real_db_manager.execute_query(raw_query)
        assert len(raw_transactions) > 0, "No transactions found"

        # Convert to TransactionModel and enhance
        print("Testing category resolution in TransactionService:")
        categorized_count = 0

        for raw_tx in raw_transactions[:5]:
            # Create basic transaction model
            import datetime
            from decimal import Decimal

            from moneywiz_mcp_server.models.transaction import (
                TransactionModel,
                TransactionType,
            )

            transaction = TransactionModel(
                id=str(raw_tx["Z_PK"]),
                entity_id=raw_tx["Z_ENT"],
                account_id=str(raw_tx["ZACCOUNT2"])
                if raw_tx["ZACCOUNT2"]
                else "unknown",
                amount=Decimal(str(raw_tx["ZAMOUNT1"]))
                if raw_tx["ZAMOUNT1"]
                else Decimal("0"),
                date=datetime.datetime.now(),  # Simplified for test
                description=raw_tx["ZDESCRIPTION"] or "No description",
                transaction_type=TransactionType.WITHDRAW,  # Simplified
                currency="USD",
            )

            # Enhance with category information
            enhanced = await transaction_service._enhance_transaction_with_metadata(
                transaction
            )

            if enhanced.category and enhanced.category != "Uncategorized":
                categorized_count += 1
                print(f"  ✅ {enhanced.description[:30]:<30} → {enhanced.category}")
            else:
                print(f"  ❌ {enhanced.description[:30]:<30} → UNCATEGORIZED")

        if categorized_count == 0:
            print("🚨 CRITICAL: TransactionService is not resolving any categories!")
            print(
                "This explains why savings recommendations show all spending as uncategorized."
            )
        else:
            print(f"✅ TransactionService resolved {categorized_count} categories")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_alternative_category_resolution_strategies(self, real_db_manager):
        """Test alternative ways to resolve categories."""
        print("Testing alternative category resolution strategies...")

        # Strategy 1: Check if table name is different
        table_names_query = """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name LIKE '%CATEGORY%'
        """
        category_tables = await real_db_manager.execute_query(table_names_query)
        print(f"Category-related tables: {[t['name'] for t in category_tables]}")

        # Strategy 2: Check for ZCATEGORYASSIGNMENT (with N)
        if any(t["name"] == "ZCATEGORYASSIGNMENT" for t in category_tables):
            print("Found ZCATEGORYASSIGNMENT (with N) - testing this table...")

            alt_query = """
            SELECT
                t.Z_PK as transaction_id,
                t.ZDESCRIPTION as description,
                ca.ZCATEGORY as category_id,
                c.ZNAME2 as category_name
            FROM ZSYNCOBJECT t
            LEFT JOIN ZCATEGORYASSIGNMENT ca ON ca.ZTRANSACTION = t.Z_PK
            LEFT JOIN ZSYNCOBJECT c ON c.Z_PK = ca.ZCATEGORY AND c.Z_ENT = 19
            WHERE t.Z_ENT IN (37, 45, 46, 47)
            AND t.ZDESCRIPTION IS NOT NULL
            LIMIT 10
            """

            try:
                alt_results = await real_db_manager.execute_query(alt_query)
                alt_categorized = sum(1 for r in alt_results if r.get("category_name"))
                print(
                    f"Alternative table results: {alt_categorized}/{len(alt_results)} categorized"
                )
            except Exception as e:
                print(f"Alternative table query failed: {e}")

        # Strategy 3: Check entity types for categories
        entity_query = """
        SELECT DISTINCT Z_ENT, COUNT(*) as count
        FROM ZSYNCOBJECT
        GROUP BY Z_ENT
        ORDER BY Z_ENT
        """
        entities = await real_db_manager.execute_query(entity_query)
        print("Entity types and counts:")
        for entity in entities:
            print(f"  Entity {entity['Z_ENT']}: {entity['count']} records")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to see print statements
