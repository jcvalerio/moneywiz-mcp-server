"""Category classification service for MoneyWiz MCP Server.

This service analyzes MoneyWiz category hierarchies to automatically detect
income vs expense categories without relying on hardcoded values.
"""

from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Any

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.transaction import TransactionType

logger = logging.getLogger(__name__)


class CategoryType(Enum):
    """Category classification types."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    UNKNOWN = "unknown"


class CategoryClassificationService:
    """Service for analyzing category hierarchies and classifying transaction types."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        # Cache for category classifications to improve performance
        self._category_type_cache: dict[int, CategoryType] = {}
        self._category_hierarchy_cache: dict[int, list[str]] = {}
        self._parent_category_cache: dict[int, int | None] = {}
        # Cache for learned statistical patterns
        self._category_patterns_cache: dict[int, dict[str, float]] = {}
        self._patterns_last_updated: datetime | None = None
        self._patterns_cache_duration = timedelta(hours=24)  # Refresh daily

    async def get_category_type(self, category_id: int) -> CategoryType:
        """
        Determine if a category represents income, expense, transfer, or adjustment.

        Args:
            category_id: MoneyWiz category ID

        Returns:
            CategoryType enum value
        """
        if category_id in self._category_type_cache:
            return self._category_type_cache[category_id]

        try:
            # Get the full category hierarchy
            hierarchy = await self._get_category_hierarchy(category_id)

            if not hierarchy:
                self._category_type_cache[category_id] = CategoryType.UNKNOWN
                return CategoryType.UNKNOWN

            # Use adaptive classification instead of hardcoded patterns
            category_type = await self._classify_category_adaptive(
                category_id, hierarchy
            )

            # Cache the result
            self._category_type_cache[category_id] = category_type

            logger.debug(
                "Classified category %s (%s) as %s",
                category_id,
                " ▶ ".join(hierarchy),
                category_type.value,
            )
            return category_type

        except Exception as e:
            logger.warning("Failed to classify category %s: %s", category_id, e)
            self._category_type_cache[category_id] = CategoryType.UNKNOWN
            return CategoryType.UNKNOWN

    async def _get_category_hierarchy(self, category_id: int) -> list[str]:
        """
        Get the full category hierarchy from root to leaf.

        Args:
            category_id: Category ID to analyze

        Returns:
            List of category names from root to leaf
        """
        if category_id in self._category_hierarchy_cache:
            return self._category_hierarchy_cache[category_id]

        hierarchy: list[str] = []
        current_id: int | None = category_id
        visited_ids = set()  # Prevent infinite loops

        try:
            while current_id and current_id not in visited_ids:
                visited_ids.add(current_id)

                # Get category name and parent
                category_query = """
                SELECT ZNAME2, ZPARENTCATEGORY
                FROM ZSYNCOBJECT
                WHERE Z_ENT = 19 AND Z_PK = ?
                """

                category_result = await self.db_manager.execute_query(
                    category_query, (current_id,)
                )

                if category_result and category_result[0]:
                    category_name = category_result[0].get("ZNAME2")
                    parent_id = category_result[0].get("ZPARENTCATEGORY")

                    if category_name:
                        hierarchy.insert(
                            0, category_name
                        )  # Add to beginning for root-to-leaf order

                    # Cache parent relationship
                    self._parent_category_cache[current_id] = parent_id

                    current_id = parent_id if isinstance(parent_id, int) else None
                else:
                    break

            # Cache the hierarchy
            self._category_hierarchy_cache[category_id] = hierarchy
            return hierarchy

        except Exception as e:
            logger.warning(
                "Failed to build category hierarchy for %s: %s", category_id, e
            )
            return []

    async def _classify_category_hierarchy(self, hierarchy: list[str]) -> CategoryType:
        """
        Classify a category hierarchy using data-driven analysis instead of hardcoded patterns.

        Uses a multi-stage approach:
        1. Statistical analysis from user's transaction history (primary)
        2. Transaction type patterns from Z_ENT values (secondary)
        3. Conservative fallback logic (tertiary)

        Args:
            hierarchy: List of category names from root to leaf

        Returns:
            CategoryType classification
        """
        if not hierarchy:
            return CategoryType.UNKNOWN

        # This method is called for specific category IDs, so we need to find the category ID
        # from the hierarchy. For now, return UNKNOWN and let the caller handle it.
        # The real logic will be in _classify_category_adaptive() method.
        return CategoryType.UNKNOWN

    async def _classify_category_adaptive(
        self, category_id: int, hierarchy: list[str]
    ) -> CategoryType:
        """
        Adaptive classification using learned patterns from user's transaction data.

        Args:
            category_id: MoneyWiz category ID
            hierarchy: Category name hierarchy

        Returns:
            CategoryType classification
        """
        try:
            # Stage 1: Use learned statistical patterns (highest confidence)
            learned_type = await self._classify_from_learned_patterns(category_id)
            if learned_type != CategoryType.UNKNOWN:
                logger.debug(
                    "Category %s classified as %s from learned patterns",
                    category_id,
                    learned_type.value,
                )
                return learned_type

            # Stage 2: Use transaction type analysis (medium confidence)
            transaction_type = await self._classify_from_transaction_types(category_id)
            if transaction_type != CategoryType.UNKNOWN:
                logger.debug(
                    "Category %s classified as %s from transaction type analysis",
                    category_id,
                    transaction_type.value,
                )
                return transaction_type

            # Stage 3: Conservative fallback (lowest confidence)
            return await self._classify_with_fallback_logic(category_id, hierarchy)

        except Exception as e:
            logger.warning(
                "Adaptive classification failed for category %s: %s", category_id, e
            )
            return CategoryType.UNKNOWN

    async def _classify_from_learned_patterns(self, category_id: int) -> CategoryType:
        """
        Classify category based on learned statistical patterns from user's transaction history.

        Args:
            category_id: Category ID to classify

        Returns:
            CategoryType based on learned patterns or UNKNOWN
        """
        # Ensure patterns are fresh
        await self._refresh_learned_patterns_if_needed()

        if category_id not in self._category_patterns_cache:
            return CategoryType.UNKNOWN

        patterns = self._category_patterns_cache[category_id]

        # Require minimum confidence and transaction count for reliable classification
        min_transactions = 5
        min_confidence = 0.8

        if patterns["transaction_count"] < min_transactions:
            return CategoryType.UNKNOWN

        positive_ratio = patterns["positive_amount_ratio"]
        confidence = patterns["confidence_score"]

        if confidence < min_confidence:
            return CategoryType.UNKNOWN

        # Classify based on amount patterns
        if positive_ratio >= 0.8:  # 80%+ positive amounts
            return CategoryType.INCOME
        elif positive_ratio <= 0.2:  # 80%+ negative amounts
            return CategoryType.EXPENSE
        else:
            # Mixed usage - could be transfer or uncertain
            return CategoryType.UNKNOWN

    async def _classify_from_transaction_types(self, category_id: int) -> CategoryType:
        """
        Classify category based on transaction type patterns (Z_ENT values).

        Args:
            category_id: Category ID to analyze

        Returns:
            CategoryType based on transaction type patterns
        """
        try:
            # Analyze which transaction types are most commonly used with this category
            type_analysis_query = """
            SELECT
                t.Z_ENT as entity_type,
                COUNT(*) as usage_count,
                AVG(CASE WHEN t.ZAMOUNT1 > 0 THEN 1.0 ELSE 0.0 END) as positive_ratio
            FROM ZSYNCOBJECT t
            LEFT JOIN ZCATEGORYASSIGMENT ca ON ca.ZTRANSACTION = t.Z_PK
            WHERE ca.ZCATEGORY = ?
            AND t.Z_ENT IN (37, 45, 46, 47, 42)  -- Transaction entities
            GROUP BY t.Z_ENT
            ORDER BY usage_count DESC
            """

            results = await self.db_manager.execute_query(
                type_analysis_query, (category_id,)
            )

            if not results:
                return CategoryType.UNKNOWN

            # Analyze the most common transaction type for this category
            primary_result = results[0]
            entity_type = primary_result["entity_type"]
            positive_ratio = primary_result["positive_ratio"]
            usage_count = primary_result["usage_count"]

            # Need minimum usage to be confident
            if usage_count < 3:
                return CategoryType.UNKNOWN

            # Map entity types to classifications
            if entity_type == 37:  # DEPOSIT
                return (
                    CategoryType.INCOME
                    if positive_ratio > 0.7
                    else CategoryType.UNKNOWN
                )
            elif entity_type == 47:  # WITHDRAW
                return (
                    CategoryType.EXPENSE
                    if positive_ratio < 0.3
                    else CategoryType.UNKNOWN
                )
            elif entity_type in [45, 46]:  # TRANSFERS
                return CategoryType.TRANSFER
            elif entity_type == 42:  # RECONCILE
                return CategoryType.ADJUSTMENT
            else:
                return CategoryType.UNKNOWN

        except Exception as e:
            logger.warning(
                "Transaction type analysis failed for category %s: %s", category_id, e
            )
            return CategoryType.UNKNOWN

    async def _classify_with_fallback_logic(
        self, category_id: int, hierarchy: list[str]
    ) -> CategoryType:
        """
        Conservative fallback classification when learned patterns are insufficient.

        Args:
            category_id: Category ID
            hierarchy: Category name hierarchy

        Returns:
            CategoryType classification with conservative defaults
        """
        try:
            # Check if category has any transactions at all
            transaction_count_query = """
            SELECT COUNT(*) as count
            FROM ZCATEGORYASSIGMENT ca
            LEFT JOIN ZSYNCOBJECT t ON t.Z_PK = ca.ZTRANSACTION
            WHERE ca.ZCATEGORY = ?
            AND t.Z_ENT IN (37, 45, 46, 47, 42)
            """

            count_result = await self.db_manager.execute_query(
                transaction_count_query, (category_id,)
            )

            if not count_result or count_result[0]["count"] == 0:
                # No transaction history - be conservative
                return CategoryType.UNKNOWN

            # If we have transaction history but couldn't classify it,
            # default to EXPENSE as most categories are expenses
            return CategoryType.EXPENSE

        except Exception as e:
            logger.warning(
                "Fallback classification failed for category %s: %s", category_id, e
            )
            return CategoryType.UNKNOWN

    async def _refresh_learned_patterns_if_needed(self) -> None:
        """Refresh learned patterns cache if it's stale."""
        now = datetime.now()

        if (
            self._patterns_last_updated is None
            or now - self._patterns_last_updated > self._patterns_cache_duration
        ):
            logger.info("Refreshing learned category patterns from transaction history")
            await self._analyze_user_transaction_patterns()
            self._patterns_last_updated = now

    async def _analyze_user_transaction_patterns(self) -> None:
        """
        Analyze user's transaction history to learn category classification patterns.

        Builds statistical model of each category's usage patterns.
        """
        try:
            # Analyze last 12 months of transactions for patterns
            analysis_query = """
            SELECT
                ca.ZCATEGORY as category_id,
                COUNT(*) as transaction_count,
                AVG(CASE WHEN t.ZAMOUNT1 > 0 THEN 1.0 ELSE 0.0 END) as positive_amount_ratio,
                AVG(ABS(t.ZAMOUNT1)) as avg_amount,
                MIN(t.ZDATE1) as first_transaction,
                MAX(t.ZDATE1) as last_transaction
            FROM ZCATEGORYASSIGMENT ca
            LEFT JOIN ZSYNCOBJECT t ON t.Z_PK = ca.ZTRANSACTION
            WHERE t.Z_ENT IN (37, 45, 46, 47, 42)  -- Transaction entities
            AND t.ZDATE1 > ? -- Last 12 months
            GROUP BY ca.ZCATEGORY
            HAVING COUNT(*) >= 2  -- Minimum transactions for analysis
            """

            # Calculate timestamp for 12 months ago (Core Data uses seconds since 2001-01-01)
            twelve_months_ago = datetime.now() - timedelta(days=365)
            base_date = datetime(2001, 1, 1)
            timestamp_12_months_ago = (twelve_months_ago - base_date).total_seconds()

            results = await self.db_manager.execute_query(
                analysis_query, (timestamp_12_months_ago,)
            )

            # Clear existing cache
            self._category_patterns_cache.clear()

            for result in results:
                category_id = result["category_id"]
                transaction_count = result["transaction_count"]
                positive_ratio = result["positive_amount_ratio"]

                # Calculate confidence score based on transaction count and consistency
                confidence_score = min(
                    1.0, transaction_count / 10.0
                )  # Max confidence at 10+ transactions

                # Adjust confidence based on ratio consistency
                if positive_ratio in [0.0, 1.0]:  # Perfect consistency
                    confidence_score *= 1.0
                elif positive_ratio < 0.1 or positive_ratio > 0.9:  # High consistency
                    confidence_score *= 0.9
                elif positive_ratio < 0.2 or positive_ratio > 0.8:  # Good consistency
                    confidence_score *= 0.8
                else:  # Mixed usage
                    confidence_score *= 0.5

                self._category_patterns_cache[category_id] = {
                    "transaction_count": transaction_count,
                    "positive_amount_ratio": positive_ratio,
                    "confidence_score": confidence_score,
                    "avg_amount": float(result["avg_amount"]),
                    "first_transaction": result["first_transaction"],
                    "last_transaction": result["last_transaction"],
                }

            logger.info(
                "Learned patterns for %s categories from transaction history",
                len(self._category_patterns_cache),
            )

        except Exception as e:
            logger.error("Failed to analyze user transaction patterns: %s", e)

    async def is_income_category(self, category_id: int) -> bool:
        """Check if a category is classified as income."""
        category_type = await self.get_category_type(category_id)
        return category_type == CategoryType.INCOME

    async def is_expense_category(self, category_id: int) -> bool:
        """Check if a category is classified as expense."""
        category_type = await self.get_category_type(category_id)
        return category_type == CategoryType.EXPENSE

    async def is_transfer_category(self, category_id: int) -> bool:
        """Check if a category is classified as transfer."""
        category_type = await self.get_category_type(category_id)
        return category_type == CategoryType.TRANSFER

    async def get_root_category_id(self, category_id: int) -> int | None:
        """
        Get the root category ID for a given category.

        Args:
            category_id: Category ID to analyze

        Returns:
            Root category ID or None if not found
        """
        current_id = category_id
        visited_ids = set()

        try:
            while current_id and current_id not in visited_ids:
                visited_ids.add(current_id)

                # Check cache first
                if current_id in self._parent_category_cache:
                    parent_id = self._parent_category_cache[current_id]
                    if parent_id is None:
                        return current_id  # This is the root
                    current_id = parent_id
                    continue

                # Query database
                category_query = """
                SELECT ZPARENTCATEGORY
                FROM ZSYNCOBJECT
                WHERE Z_ENT = 19 AND Z_PK = ?
                """

                category_result = await self.db_manager.execute_query(
                    category_query, (current_id,)
                )

                if category_result and category_result[0]:
                    parent_id = category_result[0].get("ZPARENTCATEGORY")
                    self._parent_category_cache[current_id] = parent_id

                    if parent_id is None:
                        return current_id  # This is the root
                    current_id = parent_id
                else:
                    return current_id  # No parent found, this is the root

            return None  # Circular reference or other issue

        except Exception as e:
            logger.warning("Failed to find root category for %s: %s", category_id, e)
            return None

    def clear_cache(self) -> None:
        """Clear all classification caches."""
        self._category_type_cache.clear()
        self._category_hierarchy_cache.clear()
        self._parent_category_cache.clear()
        self._category_patterns_cache.clear()
        self._patterns_last_updated = None
        logger.info("Category classification cache cleared")

    async def get_learned_patterns_stats(self) -> dict[str, Any]:
        """
        Get statistics about learned category patterns.

        Returns:
            Dictionary with learned pattern statistics
        """
        await self._refresh_learned_patterns_if_needed()

        stats: dict[str, Any] = {
            "total_learned_categories": len(self._category_patterns_cache),
            "last_updated": self._patterns_last_updated.isoformat()
            if self._patterns_last_updated
            else None,
            "categories_by_type": {
                "high_confidence_income": 0,
                "high_confidence_expense": 0,
                "mixed_usage": 0,
                "low_confidence": 0,
            },
            "avg_confidence_score": 0.0,
            "avg_transaction_count": 0.0,
        }

        if not self._category_patterns_cache:
            return stats

        total_confidence = 0.0
        total_transactions = 0.0

        for patterns in self._category_patterns_cache.values():
            confidence = patterns["confidence_score"]
            positive_ratio = patterns["positive_amount_ratio"]
            transaction_count = patterns["transaction_count"]

            total_confidence += confidence
            total_transactions += transaction_count

            # Classify category types
            if confidence >= 0.8:
                if positive_ratio >= 0.8:
                    stats["categories_by_type"]["high_confidence_income"] += 1
                elif positive_ratio <= 0.2:
                    stats["categories_by_type"]["high_confidence_expense"] += 1
                else:
                    stats["categories_by_type"]["mixed_usage"] += 1
            else:
                stats["categories_by_type"]["low_confidence"] += 1

        stats["avg_confidence_score"] = total_confidence / len(
            self._category_patterns_cache
        )
        stats["avg_transaction_count"] = total_transactions / len(
            self._category_patterns_cache
        )

        return stats

    async def analyze_all_categories(self) -> dict[str, Any]:
        """
        Analyze all categories in the database and return classification statistics.

        Returns:
            Dictionary with classification statistics and insights
        """
        try:
            # Get all categories
            categories_query = """
            SELECT Z_PK, ZNAME2, ZPARENTCATEGORY
            FROM ZSYNCOBJECT
            WHERE Z_ENT = 19 AND ZNAME2 IS NOT NULL
            ORDER BY ZNAME2
            """

            categories = await self.db_manager.execute_query(categories_query)

            if not categories:
                return {"error": "No categories found"}

            # Classify all categories
            classification_stats: dict[str, Any] = {
                "total_categories": len(categories),
                "income_categories": [],
                "expense_categories": [],
                "transfer_categories": [],
                "adjustment_categories": [],
                "unknown_categories": [],
            }

            for category in categories:
                category_id = category["Z_PK"]
                category_name = category["ZNAME2"]
                category_type = await self.get_category_type(category_id)

                category_info = {
                    "id": category_id,
                    "name": category_name,
                    "hierarchy": await self._get_category_hierarchy(category_id),
                }

                if category_type == CategoryType.INCOME:
                    classification_stats["income_categories"].append(category_info)
                elif category_type == CategoryType.EXPENSE:
                    classification_stats["expense_categories"].append(category_info)
                elif category_type == CategoryType.TRANSFER:
                    classification_stats["transfer_categories"].append(category_info)
                elif category_type == CategoryType.ADJUSTMENT:
                    classification_stats["adjustment_categories"].append(category_info)
                else:
                    classification_stats["unknown_categories"].append(category_info)

            # Add summary statistics
            classification_stats["summary"] = {
                "income_count": len(classification_stats["income_categories"]),
                "expense_count": len(classification_stats["expense_categories"]),
                "transfer_count": len(classification_stats["transfer_categories"]),
                "adjustment_count": len(classification_stats["adjustment_categories"]),
                "unknown_count": len(classification_stats["unknown_categories"]),
            }

            return classification_stats

        except Exception as e:
            logger.error("Failed to analyze categories: %s", e)
            return {"error": f"Failed to analyze categories: {e}"}
