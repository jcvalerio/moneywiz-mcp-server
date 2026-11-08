"""Service for scheduled transaction operations and occurrence tracking."""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import logging
from typing import Any

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.currency_types import CurrencyAmounts
from moneywiz_mcp_server.models.scheduled_transaction import (
    CategorySplit,
    CommitmentBreakdown,
    DisplayCurrencyTotals,
    ExchangeRateUsed,
    IncomeSource,
    RecurrenceEndCondition,
    RecurrencePattern,
    ScheduledTransactionModel,
    WeekendHandling,
)
from moneywiz_mcp_server.models.transaction import TransactionType
from moneywiz_mcp_server.services.account_kinds import (
    ACCOUNT_KIND_BY_ENTITY,
    AccountKind,
    TransferKind,
    classify_transfer,
)
from moneywiz_mcp_server.services.exchange_rate_service import ExchangeRateService
from moneywiz_mcp_server.utils.date_utils import (
    core_data_timestamp_to_datetime,
)
from moneywiz_mcp_server.utils.recurrence import (
    add_months,
    occurrence_dates,
    occurrences_between,
    parse_frequency,
    recurrence_from_duration,
)

logger = logging.getLogger(__name__)


class ScheduledEntityRole(Enum):
    """Whether a scheduled transaction handler entity represents a transfer
    between accounts or a regular scheduled transaction to a payee."""

    TRANSFER = "transfer"
    REGULAR = "regular"


# Scheduled transaction handler entities, and their ScheduledEntityRole.
# Z_ENT ids are resolved dynamically via DatabaseManager.get_entity_name_map()
# since they are not stable across MoneyWiz versions/exports.
SCHEDULED_ENTITY_ROLES: dict[str, ScheduledEntityRole] = {
    "ScheduledTransferTransactionHandler": ScheduledEntityRole.TRANSFER,
    "ScheduledDepositTransactionHandler": ScheduledEntityRole.REGULAR,
    "ScheduledWithdrawTransactionHandler": ScheduledEntityRole.REGULAR,
}

# Entity names used for supporting lookups (category, payee, tag).
CATEGORY_ENTITY_NAME = "Category"
PAYEE_ENTITY_NAME = "Payee"
TAG_ENTITY_NAME = "Tag"
# Base entity whose Z_ENT id Core Data uses to auto-generate the scheduled
# transaction <-> tag join table name/columns.
SCHEDULED_TRANSACTION_HANDLER_ENTITY_NAME = "ScheduledTransactionHandler"


class ScheduledTransactionService:
    """Service for scheduled transaction operations with occurrence tracking."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._category_cache: dict[int, str] = {}
        self._payee_cache: dict[int, str] = {}
        self._account_cache: dict[int, str] = {}
        self._tag_cache: dict[int, str] = {}
        self._scheduled_entity_roles: dict[int, ScheduledEntityRole] | None = None

    async def _get_scheduled_entity_roles(self) -> dict[int, ScheduledEntityRole]:
        """Resolve scheduled transaction handler Z_ENT ids (cached)."""
        if self._scheduled_entity_roles is None:
            entity_map = await self.db_manager.get_entity_name_map()
            self._scheduled_entity_roles = {
                entity_map[name]: role
                for name, role in SCHEDULED_ENTITY_ROLES.items()
                if name in entity_map
            }
        return self._scheduled_entity_roles

    async def _get_category_entity_id(self) -> int:
        """Resolve this database's Category Z_ENT id.

        DatabaseManager.get_entity_name_map() already caches per-connection,
        so no additional caching is needed here.
        """
        entity_map = await self.db_manager.get_entity_name_map()
        return entity_map[CATEGORY_ENTITY_NAME]

    async def _get_payee_entity_id(self) -> int:
        """Resolve this database's Payee Z_ENT id (see _get_category_entity_id)."""
        entity_map = await self.db_manager.get_entity_name_map()
        return entity_map[PAYEE_ENTITY_NAME]

    async def _get_tag_entity_id(self) -> int:
        """Resolve this database's Tag Z_ENT id (see _get_category_entity_id)."""
        entity_map = await self.db_manager.get_entity_name_map()
        return entity_map[TAG_ENTITY_NAME]

    async def _get_scheduled_tag_link_columns(self) -> tuple[str, str, str] | None:
        """Resolve the scheduled-transaction<->tag many-to-many join table.

        See DatabaseManager.resolve_join_table for why this cannot be hardcoded.
        """
        return await self.db_manager.resolve_join_table(
            SCHEDULED_TRANSACTION_HANDLER_ENTITY_NAME, TAG_ENTITY_NAME, "TAGS"
        )

    async def get_scheduled_transactions(
        self,
        account_ids: list[str] | None = None,
        categories: list[str] | None = None,
        commitment_types: list[str] | None = None,
        include_inactive: bool = False,
        limit: int | None = None,
    ) -> list[ScheduledTransactionModel]:
        """
        Get scheduled transactions with occurrence tracking.

        Args:
            account_ids: Optional list of account IDs to filter by
            categories: Optional list of category names to filter by
            commitment_types: Optional list of commitment types (finite/infinite/ending_soon)
            include_inactive: Whether to include inactive schedules
            limit: Optional limit on number of results

        Returns:
            List of ScheduledTransactionModel objects with occurrence data
        """
        try:
            logger.info("📅 Fetching scheduled transactions...")

            scheduled_transactions = []

            # Resolve this database's actual Z_ENT ids for each scheduled
            # transaction handler subtype (ids are not stable across
            # MoneyWiz versions/exports).
            entity_roles = await self._get_scheduled_entity_roles()

            for entity_type in entity_roles:
                # Repeating and one-time (ZISREPEATABLE1 = 0) schedules
                query = """
                    SELECT * FROM ZSYNCOBJECT
                    WHERE Z_ENT = ?
                """
                params = [entity_type]

                # Add active filter if needed
                if not include_inactive:
                    query += " AND ZDISABLEEXECUTION = 0"

                records = await self.db_manager.execute_query(query, tuple(params))

                if not records:
                    continue

                logger.info(
                    f"Found {len(records)} scheduled transactions for entity type {entity_type}"
                )

                for record in records:
                    try:
                        # Convert database record to ScheduledTransactionModel
                        scheduled_transaction = await self._convert_record_to_model(
                            record, entity_type, entity_roles[entity_type]
                        )

                        # Apply filters
                        if scheduled_transaction and await self._matches_filters(
                            scheduled_transaction,
                            account_ids,
                            categories,
                            commitment_types,
                        ):
                            scheduled_transactions.append(scheduled_transaction)

                    except Exception as e:
                        logger.warning(
                            f"Failed to convert record {record.get('Z_PK')} "
                            f"from entity {entity_type}: {e}"
                        )
                        continue

            # Apply limit if specified
            if limit and len(scheduled_transactions) > limit:
                scheduled_transactions = scheduled_transactions[:limit]

            logger.info(
                f"✅ Retrieved {len(scheduled_transactions)} scheduled transactions"
            )
            return scheduled_transactions

        except Exception as e:
            logger.error(f"❌ Failed to get scheduled transactions: {e}")
            raise

    async def _convert_record_to_model(
        self, record: dict[str, Any], entity_type: int, entity_role: ScheduledEntityRole
    ) -> ScheduledTransactionModel | None:
        """Convert database record to ScheduledTransactionModel."""
        try:
            # Extract basic transaction fields based on actual schema
            amount = record.get("ZAMOUNT")
            if amount is None:
                # Skip records without amount data
                return None

            # Get dates (Core Data timestamps)
            next_date_timestamp = record.get("ZEXECUTEDATE")

            if next_date_timestamp is None:
                # Skip records without scheduling data
                return None

            # Convert Core Data timestamps to datetime
            next_execution_date = core_data_timestamp_to_datetime(next_date_timestamp)

            # Get creation date
            created_timestamp = record.get("ZCREATIONDATE1") or record.get(
                "ZOBJECTCREATIONDATE"
            )
            created_date = (
                core_data_timestamp_to_datetime(created_timestamp)
                if created_timestamp
                else datetime.now()
            )

            # Get account, category, payee, and tag info based on entity type
            account_id = str(record.get("ZACCOUNT1", ""))
            recipient = record.get("ZRECIPIENTACCOUNT")
            recipient_account_id = (
                str(recipient)
                if entity_role == ScheduledEntityRole.TRANSFER and recipient
                else None
            )
            category_info = await self._get_category_info_for_scheduled(record)
            tags = await self._get_tags_for_scheduled(record)
            payee: str | None

            if entity_role == ScheduledEntityRole.TRANSFER:
                if not category_info["category"]:
                    category_info["category"] = "Transfer"
                    category_info["category_hierarchy"] = ["Transfer"]
                    category_info["category_path"] = "Transfer"
                    category_info["root_category"] = "Transfer"
                payee = "Transfer to Account"
            else:  # Regular scheduled transactions (to payees)
                if not category_info["category"]:
                    category_info["category"] = "Uncategorized"
                    category_info["category_hierarchy"] = ["Uncategorized"]
                    category_info["category_path"] = "Uncategorized"
                    category_info["root_category"] = "Uncategorized"
                payee = await self._get_payee_name(record.get("ZPAYEE1"))

            # Recurrence: unit (ZDURATIONUNITS1) and "every N" count (ZDURATION1)
            recurrence_pattern, recurrence_interval = recurrence_from_duration(
                record.get("ZDURATIONUNITS1"), record.get("ZDURATION1")
            )

            executes_count = record.get("ZEXECUTESCOUNT", 0)
            if record.get("ZISREPEATABLE1") == 0 and (executes_count or 0) > 0:
                return None  # a one-time schedule that has already run
            (
                is_one_time,
                end_condition,
                final_execution_date,
                remaining_occurrences,
            ) = self._end_of_schedule(
                record, next_execution_date, recurrence_pattern, recurrence_interval
            )

            # Generate upcoming dates
            upcoming_dates = await self._generate_upcoming_dates(
                next_execution_date,
                recurrence_pattern,
                remaining_occurrences,
                6,
                interval=recurrence_interval,
            )

            # Get description
            description = (
                record.get("ZDESC1") or f"Scheduled {category_info['category']}"
            )

            # Create the model
            scheduled_transaction = ScheduledTransactionModel(
                id=str(record.get("Z_PK", "")),
                description=description,
                amount=Decimal(str(amount)),
                currency=record.get("ZCURRENCYNAME3", "USD"),
                account_id=account_id,
                recipient_account_id=recipient_account_id,
                category=category_info["category"] or "Uncategorized",
                category_id=category_info["category_id"],
                parent_category=category_info["parent_category"],
                parent_category_id=category_info["parent_category_id"],
                root_category=category_info["root_category"],
                category_path=category_info["category_path"],
                category_hierarchy=category_info["category_hierarchy"],
                category_splits=category_info["category_splits"],
                payee=payee or "Unknown",
                transaction_type=self._infer_transaction_type(amount, entity_role),
                tags=tags,
                recurrence_pattern=recurrence_pattern,
                recurrence_interval=recurrence_interval,
                next_execution_date=next_execution_date,
                weekend_handling=self._infer_weekend_handling(record),
                end_condition=end_condition,
                total_occurrences=1 if is_one_time else None,
                completed_occurrences=executes_count,
                remaining_occurrences=remaining_occurrences,
                final_execution_date=final_execution_date,
                is_one_time=is_one_time,
                upcoming_dates=upcoming_dates,
                is_active=record.get("ZDISABLEEXECUTION", 0) == 0,
                created_date=created_date,
                last_executed_date=None,  # Would need to parse from ZEXECUTEDTRANSACTIONSDATESARRAY
                entity_type=entity_type,
                database_id=record.get("Z_PK", 0),
            )

            return scheduled_transaction

        except Exception:
            logger.exception(
                f"Failed to convert scheduled transaction Z_PK={record.get('Z_PK')}; "
                "it is omitted from results"
            )
            return None

    @staticmethod
    def _end_of_schedule(
        record: dict[str, Any],
        next_execution: datetime,
        pattern: RecurrencePattern,
        interval: int,
    ) -> tuple[bool, RecurrenceEndCondition, datetime | None, int | None]:
        """How a schedule ends: (one-time, end condition, final date, remaining).

        ZISREPEATABLE1 = 0 marks a one-time schedule, which runs once on its
        next execution date. A repeating schedule that ends ("after N
        repeats" or "on date") stores its last date in ZLASTEXECUTEDATE.
        """
        if record.get("ZISREPEATABLE1") == 0:
            return True, RecurrenceEndCondition.AFTER_OCCURRENCES, next_execution, 1
        last = record.get("ZLASTEXECUTEDATE")
        if last is None:
            return False, RecurrenceEndCondition.NEVER, None, None
        final = core_data_timestamp_to_datetime(last)
        # Compare calendar days: the stored end may differ in time of day.
        remaining = sum(
            1
            for d in occurrence_dates(
                next_execution, pattern, interval, until=final + timedelta(days=1)
            )
            if d.date() <= final.date()
        )
        return False, RecurrenceEndCondition.ON_DATE, final, remaining

    async def _matches_filters(
        self,
        transaction: ScheduledTransactionModel,
        account_ids: list[str] | None,
        categories: list[str] | None,
        commitment_types: list[str] | None,
    ) -> bool:
        """Check if transaction matches the specified filters."""
        if account_ids and transaction.account_id not in account_ids:
            return False

        if categories and transaction.category not in categories:
            return False

        if commitment_types and transaction.commitment_type not in commitment_types:
            return False

        return True

    def _infer_weekend_handling(self, record: dict[str, Any]) -> WeekendHandling:
        """Infer weekend handling from ZWEEKENDSHANDLER field."""
        weekend_handler = record.get("ZWEEKENDSHANDLER", 2)

        handlers = {
            0: WeekendHandling.SAME_DAY,
            1: WeekendHandling.PREVIOUS_WEEKDAY,
            2: WeekendHandling.NEXT_WEEKDAY,
        }
        return handlers.get(weekend_handler, WeekendHandling.SAME_DAY)

    async def _get_category_info_for_scheduled(
        self, record: dict[str, Any]
    ) -> dict[str, Any]:
        """Main category, its hierarchy, and every split of a scheduled transaction.

        A schedule can be split across several categories, each with its own
        amount (e.g. a loan payment: principal, interest and insurance). The
        main category is the split with the largest amount; all splits are
        returned in "category_splits" when there is more than one.
        """
        assignments = await self._get_category_assignments(record)
        category_id = self._primary_category_id(assignments)
        if category_id is None:
            return self._empty_category_info()

        info = await self._build_category_info(category_id)
        if len(assignments) > 1:
            splits = []
            for split_id, amount in assignments:
                split_info = await self._build_category_info(split_id)
                splits.append(
                    CategorySplit(
                        category=split_info["category"] or "Uncategorized",
                        category_id=split_id,
                        category_path=split_info["category_path"],
                        amount=abs(amount) if amount is not None else None,
                    )
                )
            info["category_splits"] = splits
        return info

    async def _get_category_id_for_scheduled(
        self, record: dict[str, Any]
    ) -> int | None:
        """The main category ID of a scheduled transaction (largest split)."""
        return self._primary_category_id(await self._get_category_assignments(record))

    @staticmethod
    def _primary_category_id(
        assignments: list[tuple[int, Decimal | None]],
    ) -> int | None:
        """The category with the largest amount; the first stored on a tie."""
        if not assignments:
            return None
        return max(assignments, key=lambda a: abs(a[1] or Decimal(0)))[0]

    async def _get_category_assignments(
        self, record: dict[str, Any]
    ) -> list[tuple[int, Decimal | None]]:
        """(category ID, split amount) for each category of a scheduled transaction."""
        scheduled_id = record.get("Z_PK")
        if scheduled_id:
            try:
                # MoneyWiz stores scheduled category links in ZCATEGORYASSIGMENT,
                # one row per category with that category's share in ZAMOUNT.
                # Column names keep MoneyWiz/Core Data's misspelling of "TRANSACITION".
                # Join on ZSCHEDULEDTRANSACITION (the Z_PK) only: the sibling
                # Z<n>_SCHEDULEDTRANSACITION column holds the target's Z_ENT, and
                # its name changes with the model's entity ids.
                category_assignment_query = """
                SELECT ca.ZCATEGORY, ca.ZAMOUNT
                FROM ZCATEGORYASSIGMENT ca
                WHERE ca.ZSCHEDULEDTRANSACITION = ?
                ORDER BY ca.Z_PK
                """
                rows = await self.db_manager.execute_query(
                    category_assignment_query, (scheduled_id,)
                )
                assignments = [
                    (
                        row["ZCATEGORY"],
                        Decimal(str(row["ZAMOUNT"]))
                        if row.get("ZAMOUNT") is not None
                        else None,
                    )
                    for row in rows or []
                    if isinstance(row.get("ZCATEGORY"), int)
                ]
                if assignments:
                    return assignments

            except Exception as e:
                logger.warning(
                    f"Failed to resolve scheduled category for {scheduled_id}: {e}"
                )

        for field_name in ("ZCATEGORY", "ZCATEGORY1", "ZCATEGORY2"):
            category_id = record.get(field_name)
            if isinstance(category_id, int):
                return [(category_id, None)]

        return []

    @staticmethod
    def _empty_category_info() -> dict[str, Any]:
        """Return default empty category hierarchy information."""
        return {
            "category": None,
            "category_id": None,
            "parent_category": None,
            "parent_category_id": None,
            "root_category": None,
            "category_path": None,
            "category_hierarchy": [],
            "category_splits": [],
        }

    async def _build_category_info(self, category_id: int) -> dict[str, Any]:
        """Build category hierarchy information for a category ID."""
        hierarchy = await self._get_category_hierarchy(category_id)
        if not hierarchy:
            return self._empty_category_info()

        hierarchy_names = [item["name"] for item in hierarchy]
        parent = hierarchy[-2] if len(hierarchy) > 1 else None

        return {
            "category": hierarchy_names[-1],
            "category_id": hierarchy[-1]["id"],
            "parent_category": parent["name"] if parent else None,
            "parent_category_id": parent["id"] if parent else None,
            "root_category": hierarchy_names[0],
            "category_path": " ▶ ".join(hierarchy_names),
            "category_hierarchy": hierarchy_names,
            "category_splits": [],
        }

    async def _get_category_hierarchy(self, category_id: int) -> list[dict[str, Any]]:
        """Get category hierarchy from root to leaf."""
        hierarchy: list[dict[str, Any]] = []
        current_id: int | None = category_id
        visited_ids = set()
        category_entity_id = await self._get_category_entity_id()

        while current_id and current_id not in visited_ids:
            visited_ids.add(current_id)

            query = """
            SELECT Z_PK, ZNAME2, ZPARENTCATEGORY
            FROM ZSYNCOBJECT
            WHERE Z_ENT = ? AND Z_PK = ?
            """
            result = await self.db_manager.execute_query(
                query, (category_entity_id, current_id)
            )
            if not result:
                break

            category_row = result[0]
            category_name = category_row.get("ZNAME2")
            if category_name:
                hierarchy.insert(0, {"id": current_id, "name": category_name})

            parent_id = category_row.get("ZPARENTCATEGORY")
            current_id = parent_id if isinstance(parent_id, int) else None

        return hierarchy

    def _infer_transaction_type(
        self,
        amount: float,
        entity_role: ScheduledEntityRole = ScheduledEntityRole.REGULAR,
    ) -> TransactionType:
        """Infer transaction type from the entity role and amount sign."""
        if entity_role == ScheduledEntityRole.TRANSFER:
            return (
                TransactionType.TRANSFER_OUT
                if amount < 0
                else TransactionType.TRANSFER_IN
            )
        if amount > 0:
            return TransactionType.DEPOSIT  # Positive amount = money coming in
        else:
            return TransactionType.WITHDRAW  # Negative amount = money going out

    async def _generate_upcoming_dates(
        self,
        next_date: datetime,
        pattern: RecurrencePattern,
        remaining_occurrences: int | None,
        months_ahead: int = 6,
        interval: int = 1,
    ) -> list[datetime]:
        """Generate upcoming execution dates within the next months_ahead months."""
        limit = 20  # Cap for performance
        if remaining_occurrences is not None:
            limit = min(limit, remaining_occurrences)
        return occurrence_dates(
            next_date,
            pattern,
            interval,
            until=add_months(datetime.now(), months_ahead),
            limit=limit,
        )

    async def _get_category_name(self, category_id: int | None) -> str | None:
        """Get category name from cache or database."""
        if not category_id:
            return None

        if category_id in self._category_cache:
            return self._category_cache[category_id]

        try:
            category_entity_id = await self._get_category_entity_id()
            query = "SELECT ZNAME2 FROM ZSYNCOBJECT WHERE Z_ENT = ? AND Z_PK = ?"
            result = await self.db_manager.execute_query(
                query, (category_entity_id, category_id)
            )
            if result:
                category_name: str = result[0].get("ZNAME2", "Unknown")
                self._category_cache[category_id] = category_name
                return category_name
        except Exception as e:
            logger.warning(f"Failed to get category name for {category_id}: {e}")

        return None

    async def _get_payee_name(self, payee_id: int | None) -> str | None:
        """Get payee name from cache or database."""
        if not payee_id:
            return None

        if payee_id in self._payee_cache:
            return self._payee_cache[payee_id]

        try:
            payee_entity_id = await self._get_payee_entity_id()
            query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? AND Z_PK = ?"
            result = await self.db_manager.execute_query(
                query, (payee_entity_id, payee_id)
            )
            if result:
                payee_name = self._extract_payee_name(result[0], payee_id)
                self._payee_cache[payee_id] = payee_name
                return payee_name
        except Exception as e:
            logger.warning(f"Failed to get payee name for {payee_id}: {e}")

        return None

    async def _get_tags_for_scheduled(self, record: dict[str, Any]) -> list[str]:
        """Get tag names for a scheduled transaction."""
        scheduled_id = record.get("Z_PK")
        if not scheduled_id:
            return []

        link_columns = await self._get_scheduled_tag_link_columns()
        if link_columns is None:
            return []
        table_name, scheduled_column, tag_column = link_columns

        try:
            tag_query = f"""
            SELECT {tag_column} AS tag_id
            FROM {table_name}
            WHERE {scheduled_column} = ?
            """  # nosec: B608 - identifiers validated by resolve_join_table
            tag_results = await self.db_manager.execute_query(
                tag_query, (scheduled_id,)
            )
        except Exception as e:
            logger.warning(f"Failed to get scheduled tags for {scheduled_id}: {e}")
            return []

        tag_names: list[str] = []
        for tag_result in tag_results:
            tag_id = tag_result.get("tag_id")
            if tag_id is None:
                continue

            tag_name = await self._get_tag_name(tag_id)
            if tag_name and tag_name != "NULL":
                tag_names.append(tag_name)

        return tag_names

    async def _get_tag_name(self, tag_id: int) -> str:
        """Get tag name from cache or database."""
        if tag_id in self._tag_cache:
            return self._tag_cache[tag_id]

        try:
            tag_entity_id = await self._get_tag_entity_id()
            query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? AND Z_PK = ?"
            result = await self.db_manager.execute_query(query, (tag_entity_id, tag_id))
            if result:
                tag_name = self._extract_tag_name(result[0], tag_id)
            else:
                tag_name = f"Tag_{tag_id}"
        except Exception as e:
            logger.warning(f"Failed to get tag name for {tag_id}: {e}")
            tag_name = f"Tag_{tag_id}"

        self._tag_cache[tag_id] = tag_name
        return tag_name

    @staticmethod
    def _extract_tag_name(tag_row: dict[str, Any], tag_id: int) -> str:
        """Extract a tag name from schema-dependent MoneyWiz tag fields."""
        for field_name in (
            "ZNAME6",
            "ZNAME2",
            "ZNAME",
            "ZDESC2",
            "ZDESC",
            "ZVALUE",
            "ZGID",
        ):
            value = tag_row.get(field_name)
            if value:
                return str(value)

        return f"Tag_{tag_id}"

    @staticmethod
    def _extract_payee_name(payee_row: dict[str, Any], payee_id: int) -> str:
        """Extract a payee name from schema-dependent MoneyWiz payee fields."""
        for field_name in (
            "ZNAME5",
            "ZNAME2",
            "ZNAME",
            "ZDESC2",
            "ZDESC",
            "ZVALUE",
            "ZGID",
        ):
            value = payee_row.get(field_name)
            if value:
                return str(value)

        return f"Payee_{payee_id}"

    async def _get_account_kinds(self) -> dict[str, AccountKind]:
        """Account Z_PK (as str) -> kind, from each account's entity type."""
        entity_map = await self.db_manager.get_entity_name_map()
        kind_by_ent = {
            entity_map[name]: kind
            for name, kind in ACCOUNT_KIND_BY_ENTITY.items()
            if name in entity_map
        }
        if not kind_by_ent:
            return {}
        placeholders = ",".join("?" for _ in kind_by_ent)
        rows = await self.db_manager.execute_query(
            f"SELECT Z_PK, Z_ENT FROM ZSYNCOBJECT WHERE Z_ENT IN ({placeholders})",  # nosec B608 - placeholders only
            tuple(kind_by_ent),
        )
        return {str(row["Z_PK"]): kind_by_ent[row["Z_ENT"]] for row in rows}

    @staticmethod
    def _transfer_kind(
        transfer: ScheduledTransactionModel,
        account_kinds: dict[str, AccountKind],
    ) -> TransferKind:
        """Kind of a scheduled transfer from its accounts' MoneyWiz types."""
        source, destination = transfer.account_id, transfer.recipient_account_id
        if transfer.transaction_type == TransactionType.TRANSFER_IN:
            source, destination = destination, source
        return classify_transfer(
            account_kinds.get(source or ""), account_kinds.get(destination or "")
        )

    async def calculate_salary_breakdown(
        self,
        next_salary_date: datetime,
        salary_amount: Decimal | None = None,
        planning_horizon_months: int = 3,
        salary_currency: str | None = None,
        salary_frequency: str | None = None,
        display_currency: str | None = None,
        exchange_rates: dict[str, float] | None = None,
        count_savings_as_commitments: bool = True,
    ) -> dict[str, Any]:
        """
        Compare income with outgoing commitments over a planning period.

        The period is [next_salary_date, next_salary_date + horizon months).

        Income is every scheduled deposit in the period, in its own currency
        (a salary in one currency and other income in another both count).
        If salary_amount is given, it replaces the scheduled income in
        salary_currency only; its payments are counted from salary_frequency,
        else from the scheduled deposit in that currency, else monthly.

        Commitments are scheduled withdrawals plus the scheduled transfers
        that are obligations, classified from MoneyWiz account types (see
        services/account_kinds.py): bank -> Loan payments, and bank ->
        Investment contributions unless count_savings_as_commitments is
        False. Credit card payments, internal moves and transfers out of a
        card or loan don't count (the card's expenses are already the
        scheduled withdrawals charged to it); every transfer is still
        reported by kind.

        Amounts stay in their native currency; combined totals are also
        given in display_currency using MoneyWiz's latest exchange rates,
        overridable via exchange_rates (units per 1 display_currency).

        Raises:
            ValueError: invalid frequency, rate, or an undeterminable currency.
        """
        logger.info("💰 Calculating salary breakdown")

        scheduled_transactions = await self.get_scheduled_transactions()
        period_start = next_salary_date
        period_end = add_months(next_salary_date, planning_horizon_months)

        def in_period(t: ScheduledTransactionModel) -> list[datetime]:
            return occurrences_between(
                t.next_execution_date,
                t.recurrence_pattern,
                t.recurrence_interval,
                period_start,
                period_end,
                max_occurrences=t.remaining_occurrences,
            )

        deposits = [
            t
            for t in scheduled_transactions
            if t.transaction_type == TransactionType.DEPOSIT
        ]
        withdrawals = [
            t
            for t in scheduled_transactions
            if t.transaction_type == TransactionType.WITHDRAW
        ]
        transfers = [
            t
            for t in scheduled_transactions
            if t.transaction_type
            in (TransactionType.TRANSFER_OUT, TransactionType.TRANSFER_IN)
        ]

        rates = await ExchangeRateService(self.db_manager).get_rates()

        # --- Income -------------------------------------------------------
        income_sources: list[IncomeSource] = []
        salary_per_payment: dict[str, Decimal] = {}

        if salary_amount is not None:
            salary_currency = (
                salary_currency
                or (
                    max(deposits, key=lambda t: abs(t.amount)).currency
                    if len({t.currency for t in deposits}) == 1
                    else None
                )
                or rates.anchor
                # Last resort: every schedule uses the same currency.
                or (
                    scheduled_transactions[0].currency
                    if len({t.currency for t in scheduled_transactions}) == 1
                    else None
                )
            )
            if not salary_currency:
                raise ValueError(
                    "salary_currency is required: it cannot be inferred from "
                    "this database"
                )
            salary_currency = salary_currency.upper()

            same_currency = [t for t in deposits if t.currency == salary_currency]
            if salary_frequency:
                pattern, interval = parse_frequency(salary_frequency)
            elif same_currency:
                main = max(same_currency, key=lambda t: abs(t.amount))
                pattern, interval = main.recurrence_pattern, main.recurrence_interval
            else:
                pattern, interval = RecurrencePattern.MONTHLY, 1

            paychecks = occurrences_between(
                next_salary_date, pattern, interval, period_start, period_end
            )
            income_sources.append(
                IncomeSource(
                    description="Salary (provided)",
                    currency=salary_currency,
                    amount_per_payment=salary_amount,
                    payments_in_period=len(paychecks),
                    total_in_period=salary_amount * len(paychecks),
                    recurrence_pattern=pattern.value,
                    recurrence_interval=interval,
                    source="provided",
                )
            )
            salary_per_payment[salary_currency] = salary_amount
            # The provided salary replaces scheduled income in its currency.
            replaced = [
                t.description
                for t in deposits
                if t.currency == salary_currency and in_period(t)
            ]
            deposits = [t for t in deposits if t.currency != salary_currency]
        else:
            replaced = []
            if salary_frequency:
                parse_frequency(salary_frequency)  # validate even if unused

        for t in deposits:
            dates = in_period(t)
            if not dates:
                continue
            amount = abs(t.amount)
            income_sources.append(
                IncomeSource(
                    description=t.description,
                    currency=t.currency,
                    amount_per_payment=amount,
                    payments_in_period=len(dates),
                    total_in_period=amount * len(dates),
                    recurrence_pattern=t.recurrence_pattern.value,
                    recurrence_interval=t.recurrence_interval,
                    source="scheduled",
                )
            )
            if salary_amount is None:
                current = salary_per_payment.get(t.currency, Decimal("0"))
                salary_per_payment[t.currency] = max(current, amount)

        income_by_currency: dict[str, Decimal] = {}
        for source in income_sources:
            income_by_currency[source.currency] = (
                income_by_currency.get(source.currency, Decimal("0"))
                + source.total_in_period
            )

        # --- Commitments --------------------------------------------------
        finite_commitments: list[CommitmentBreakdown] = []
        infinite_commitments: list[CommitmentBreakdown] = []
        ending_soon_commitments: list[CommitmentBreakdown] = []
        commitments_by_currency: dict[str, Decimal] = {}

        account_kinds = await self._get_account_kinds() if transfers else {}
        transfers_by_kind: dict[str, dict[str, Decimal]] = {}
        unclassified: list[str] = []
        counted: list[tuple[ScheduledTransactionModel, str, list[datetime]]] = [
            (t, "expense", in_period(t)) for t in withdrawals
        ]
        for t in transfers:
            dates = in_period(t)
            if not dates:
                continue
            kind = self._transfer_kind(t, account_kinds)
            bucket = transfers_by_kind.setdefault(kind.value, {})
            bucket[t.currency] = bucket.get(t.currency, Decimal("0")) + abs(
                t.amount
            ) * len(dates)
            if kind is TransferKind.UNCLASSIFIED:
                unclassified.append(t.description)
            elif kind is TransferKind.DEBT_PAYMENT or (
                kind is TransferKind.SAVINGS and count_savings_as_commitments
            ):
                counted.append((t, kind.value, dates))

        commitments_by_kind: dict[str, dict[str, Decimal]] = {}
        for t, commitment_kind, dates in counted:
            if not dates:
                continue
            amount = abs(t.amount)
            total_impact = amount * len(dates)
            commitment = CommitmentBreakdown(
                description=t.description,
                amount=amount,
                currency=t.currency,
                category=t.category,
                next_date=t.next_execution_date,
                remaining_payments=t.remaining_occurrences,
                final_payment_date=t.final_execution_date,
                payments_in_period=len(dates),
                total_impact_in_period=total_impact,
                commitment_type=t.commitment_type,
                urgency_level=t.urgency_level,
                kind=commitment_kind,
                category_splits=t.category_splits,
            )
            by_kind = commitments_by_kind.setdefault(commitment_kind, {})
            by_kind[t.currency] = by_kind.get(t.currency, Decimal("0")) + total_impact
            if t.commitment_type == "ending_soon":
                ending_soon_commitments.append(commitment)
            elif t.commitment_type in ("finite", "one_time"):
                finite_commitments.append(commitment)
            else:
                infinite_commitments.append(commitment)
            commitments_by_currency[t.currency] = (
                commitments_by_currency.get(t.currency, Decimal("0")) + total_impact
            )

        currencies = sorted(set(income_by_currency) | set(commitments_by_currency))
        remaining_by_currency = {
            c: income_by_currency.get(c, Decimal("0"))
            - commitments_by_currency.get(c, Decimal("0"))
            for c in currencies
        }

        # --- Combined totals in one currency ------------------------------
        display = (
            (display_currency or "").upper()
            or (
                salary_currency.upper()
                if salary_amount is not None and salary_currency
                else None
            )
            or rates.anchor
        )
        if display is None and len(currencies) == 1:
            display = currencies[0]

        totals = None
        rates_used: list[ExchangeRateUsed] = []
        without_rate: list[str] = []
        if display:
            display_rates = rates.rebase(display).with_overrides(exchange_rates)
            income_total = commitments_total = Decimal("0")
            for c in currencies:
                if c != display and not display_rates.has(c):
                    without_rate.append(c)
                    continue
                income_total += display_rates.convert(
                    income_by_currency.get(c, Decimal("0")), c
                ) or Decimal("0")
                commitments_total += display_rates.convert(
                    commitments_by_currency.get(c, Decimal("0")), c
                ) or Decimal("0")
                if c != display:
                    info = display_rates.rates[c]
                    rates_used.append(
                        ExchangeRateUsed(
                            currency=c,
                            units_per_display_currency=float(info.units_per_anchor),
                            as_of=info.as_of,
                            source=info.source,
                        )
                    )
            totals = DisplayCurrencyTotals(
                currency=display,
                income=round(float(income_total), 2),
                commitments=round(float(commitments_total), 2),
                remaining=round(float(income_total - commitments_total), 2),
            )
            coverage_analysis = (
                "incomplete"
                if without_rate
                else self._coverage(income_total, commitments_total)
            )
        else:
            coverage_analysis = "unknown"

        recommendations = self._generate_salary_recommendations(
            coverage_analysis,
            ending_soon_commitments,
            finite_commitments,
            has_income=bool(income_sources),
            without_rate=without_rate,
            unclassified=unclassified,
            replaced_income=replaced,
        )
        commitment_end_analysis = self._analyze_commitment_endings(
            finite_commitments + ending_soon_commitments
        )

        return {
            "salary_amount": CurrencyAmounts(salary_per_payment),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "next_salary_date": next_salary_date.isoformat(),
            "total_commitments_in_period": CurrencyAmounts(commitments_by_currency),
            "finite_commitments": finite_commitments,
            "infinite_commitments": infinite_commitments,
            "ending_soon_commitments": ending_soon_commitments,
            "remaining_after_commitments": CurrencyAmounts(remaining_by_currency),
            "coverage_analysis": coverage_analysis,
            "commitment_end_analysis": commitment_end_analysis,
            "recommendations": recommendations,
            "income_in_period": CurrencyAmounts(income_by_currency),
            "income_sources": income_sources,
            "commitments_by_kind": {
                k: CurrencyAmounts(v) for k, v in commitments_by_kind.items()
            },
            "transfers_in_period": {
                k: CurrencyAmounts(v) for k, v in transfers_by_kind.items()
            },
            "unclassified_transfers": unclassified,
            "display_currency": display,
            "totals_in_display_currency": totals,
            "exchange_rates_used": rates_used,
            "currencies_without_rate": without_rate,
        }

    @staticmethod
    def _coverage(income: Decimal, commitments: Decimal) -> str:
        """sufficient: >= 10% of income left; tight: 0-10% left;
        insufficient: commitments exceed income; unknown: no income."""
        if income <= 0:
            return "unknown"
        remaining = income - commitments
        if remaining < 0:
            return "insufficient"
        if remaining < income * Decimal("0.1"):
            return "tight"
        return "sufficient"

    @staticmethod
    def _format_by_currency(amounts: dict[str, Decimal]) -> str:
        return " + ".join(
            f"{amount:,.2f} {code}" for code, amount in sorted(amounts.items())
        )

    def _generate_salary_recommendations(
        self,
        coverage_analysis: str,
        ending_soon: list[CommitmentBreakdown],
        finite: list[CommitmentBreakdown],
        has_income: bool = True,
        without_rate: list[str] | None = None,
        unclassified: list[str] | None = None,
        replaced_income: list[str] | None = None,
    ) -> list[str]:
        """Generate salary recommendations; amounts are kept per currency."""
        recommendations = []

        if not has_income:
            recommendations.append(
                "📌 No income found in this period. Pass salary_amount (and "
                "salary_currency) or schedule your income in MoneyWiz."
            )
        if coverage_analysis == "insufficient":
            recommendations.append(
                "⚠️ Your commitments exceed your income for this period. "
                "Consider reducing expenses or increasing income."
            )
        if coverage_analysis == "tight":
            recommendations.append(
                "💡 Less than 10% of your income is left after commitments. "
                "Monitor expenses carefully this period."
            )
        if without_rate:
            recommendations.append(
                f"📌 No exchange rate for {', '.join(without_rate)}; those "
                "amounts are excluded from the combined totals, so there is "
                "no coverage verdict (incomplete). Pass exchange_rates to "
                "include them."
            )
        if replaced_income:
            recommendations.append(
                "📌 The provided salary replaces the scheduled income in its "
                f"currency: {', '.join(sorted(set(replaced_income)))}. Leave "
                "salary_amount out to count every scheduled deposit."
            )

        if unclassified:
            recommendations.append(
                f"📌 {len(unclassified)} scheduled transfers connect account "
                "types that fit no rule and are left out of commitments: "
                f"{', '.join(sorted(set(unclassified)))}. Check those account "
                "types in MoneyWiz."
            )

        if ending_soon:
            relief: dict[str, Decimal] = {}
            for c in ending_soon:
                relief[c.currency] = relief.get(c.currency, Decimal("0")) + c.amount
            recommendations.append(
                f"🎉 {len(ending_soon)} commitments ending soon will free up "
                f"{self._format_by_currency(relief)} per payment."
            )

        if finite:
            avg_end_time = sum(c.remaining_payments or 0 for c in finite) / len(finite)
            recommendations.append(
                f"📅 {len(finite)} finite commitments will end in ~{avg_end_time:.0f} payments on average."
            )

        return recommendations

    def _analyze_commitment_endings(
        self, commitments: list[CommitmentBreakdown]
    ) -> str:
        """Analyze when commitments will end and their impact."""
        if not commitments:
            return "No finite commitments found."

        ending_this_year = []
        ending_later = []

        for commitment in commitments:
            if (
                commitment.final_payment_date
                and commitment.final_payment_date.year == datetime.now().year
            ):
                ending_this_year.append(commitment)
            else:
                ending_later.append(commitment)

        analysis = f"{len(ending_this_year)} commitments ending this year"
        if ending_later:
            analysis += f", {len(ending_later)} ending later"

        return analysis
