"""Unit tests for dynamic Core Data entity resolution against real SQLite files."""

from collections.abc import AsyncIterator, Callable
import sqlite3

import pytest

from moneywiz_mcp_server.database.connection import DatabaseManager


def _build_db(path, entities: dict[str, int], statements: list[str]) -> str:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER, Z_NAME VARCHAR)")
    conn.executemany(
        "INSERT INTO Z_PRIMARYKEY (Z_ENT, Z_NAME) VALUES (?, ?)",
        [(ent, name) for name, ent in entities.items()],
    )
    for statement in statements:
        conn.execute(statement)
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
async def open_db(tmp_path) -> AsyncIterator[Callable]:
    managers: list[DatabaseManager] = []

    async def _open(entities: dict[str, int], statements: list[str]):
        db_path = _build_db(
            tmp_path / f"db{len(managers)}.sqlite", entities, statements
        )
        manager = DatabaseManager(db_path, read_only=True)
        await manager.initialize()
        managers.append(manager)
        return manager

    yield _open
    for manager in managers:
        await manager.close()


class TestEntityResolution:
    """get_entity_name_map and resolve_join_table on concrete schemas."""

    @pytest.mark.unit
    async def test_entity_name_map_reads_this_databases_ids(self, open_db):
        db = await open_db({"WithdrawTransaction": 52, "Category": 21}, [])

        assert await db.get_entity_name_map() == {
            "WithdrawTransaction": 52,
            "Category": 21,
        }

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("transaction_ent", "tag_ent"),
        [(36, 35), (37, 36)],
        ids=["model-a", "model-b"],
    )
    async def test_resolves_transaction_tag_table_for_each_model(
        self, open_db, transaction_ent, tag_ent
    ):
        table = f"Z_{transaction_ent}TAGS"
        db = await open_db(
            {"Transaction": transaction_ent, "Tag": tag_ent},
            [
                f"CREATE TABLE {table} "
                f"(Z_{transaction_ent}TRANSACTIONS INTEGER, Z_{tag_ent}TAGS INTEGER)"
            ],
        )

        assert await db.resolve_join_table("Transaction", "Tag", "TAGS") == (
            table,
            f"Z_{transaction_ent}TRANSACTIONS",
            f"Z_{tag_ent}TAGS",
        )

    @pytest.mark.unit
    async def test_picks_the_table_for_the_requested_owner(self, open_db):
        # A scheduled-transaction tag table sits beside the transaction one
        db = await open_db(
            {"ScheduledTransactionHandler": 31, "Tag": 35, "Transaction": 36},
            [
                "CREATE TABLE Z_31TAGS "
                "(Z_31SCHEDULEDTRANSACTIONS1 INTEGER, Z_35TAGS2 INTEGER)",
                "CREATE TABLE Z_36TAGS (Z_36TRANSACTIONS INTEGER, Z_35TAGS INTEGER)",
            ],
        )

        assert await db.resolve_join_table(
            "ScheduledTransactionHandler", "Tag", "TAGS"
        ) == ("Z_31TAGS", "Z_31SCHEDULEDTRANSACTIONS1", "Z_35TAGS2")
        assert await db.resolve_join_table("Transaction", "Tag", "TAGS") == (
            "Z_36TAGS",
            "Z_36TRANSACTIONS",
            "Z_35TAGS",
        )

    @pytest.mark.unit
    async def test_returns_none_when_entity_is_missing(self, open_db):
        db = await open_db({"Transaction": 36}, [])

        assert await db.resolve_join_table("Transaction", "Tag", "TAGS") is None

    @pytest.mark.unit
    async def test_skips_tables_with_unsafe_identifiers(self, open_db):
        # Names are interpolated into SQL by callers, so anything that is not
        # a plain Core Data identifier must never be returned.
        db = await open_db(
            {"Transaction": 36, "Tag": 35},
            [
                'CREATE TABLE "Z_36TAGS; DROP TABLE ZSYNCOBJECT; --TAGS" '
                "(Z_36TRANSACTIONS INTEGER, Z_35TAGS INTEGER)",
            ],
        )

        assert await db.resolve_join_table("Transaction", "Tag", "TAGS") is None
