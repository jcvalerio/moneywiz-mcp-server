"""Transaction service for MoneyWiz MCP Server."""

from datetime import datetime
from decimal import Decimal
import logging
from typing import Any

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.analytics_result import (
    CategoryExpense,
    IncomeExpenseAnalysis,
)
from moneywiz_mcp_server.models.transaction import (
    DateRange,
    TransactionModel,
    TransactionType,
)
from moneywiz_mcp_server.utils.date_utils import datetime_to_core_data_timestamp

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for transaction operations and analysis."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._category_cache: dict[int, str] = {}
        self._payee_cache: dict[int, str] = {}
        self._account_currency_cache: dict[int, str] = {}
        self._tag_cache: dict[int, str] = {}  # Cache for tag names

    async def get_transactions(
        self,
        start_date: datetime,
        end_date: datetime,
        account_ids: list[int] | None = None,
        categories: list[str] | None = None,
        transaction_types: list[TransactionType] | None = None,
        limit: int | None = None,
    ) -> list[TransactionModel]:
        """
        Get transactions with filtering options.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            account_ids: Optional list of account IDs to filter
            categories: Optional list of category names to filter
            transaction_types: Optional list of transaction types to filter
            limit: Optional limit on number of results

        Returns:
            List of TransactionModel objects
        """
        try:
            # Convert dates to Core Data timestamps
            start_timestamp = datetime_to_core_data_timestamp(start_date)
            end_timestamp = datetime_to_core_data_timestamp(end_date)

            # Build base query for transaction entities
            transaction_entities = [37, 45, 46, 47]  # Core transaction types

            # Add investment entities if needed
            if transaction_types:
                investment_types = [
                    TransactionType.INVESTMENT_BUY,
                    TransactionType.INVESTMENT_SELL,
                    TransactionType.INVESTMENT_EXCHANGE,
                ]
                if any(tt in investment_types for tt in transaction_types):
                    transaction_entities.extend([38, 40, 41])
                if TransactionType.REFUND in transaction_types:
                    transaction_entities.append(43)
                if TransactionType.RECONCILE in transaction_types:
                    transaction_entities.append(42)
                if TransactionType.TRANSFER_BUDGET in transaction_types:
                    transaction_entities.append(44)
            else:
                # Include all transaction types by default
                transaction_entities.extend([38, 40, 41, 42, 43, 44])

            # Build WHERE conditions using safe parameter substitution
            entity_placeholders = ",".join("?" for _ in transaction_entities)
            where_conditions = [
                f"Z_ENT IN ({entity_placeholders})",  # nosec: B608 - Safe placeholder substitution
                "ZDATE1 >= ?",
                "ZDATE1 <= ?",
            ]
            params = [*list(transaction_entities), start_timestamp, end_timestamp]

            # Add account filter
            if account_ids:
                account_placeholders = ",".join("?" for _ in account_ids)
                where_conditions.append(f"ZACCOUNT2 IN ({account_placeholders})")  # nosec: B608 - Safe placeholder substitution
                params.extend(account_ids)

            # Build final query using safe parameter substitution
            # nosec: B608 - Safe use of .format() with parameterized WHERE conditions
            base_query = """
            SELECT * FROM ZSYNCOBJECT
            WHERE {}
            ORDER BY ZDATE1 DESC
            """.format(" AND ".join(where_conditions))  # nosec

            if limit:
                query = base_query + " LIMIT ?"
                params.append(limit)
            else:
                query = base_query

            logger.debug(f"Executing transaction query with {len(params)} parameters")

            # Execute query
            rows = await self.db_manager.execute_query(query, params)

            # Convert to TransactionModel objects
            transactions = []
            for row in rows:
                try:
                    transaction = TransactionModel.from_raw_data(row)

                    # Enhance with category and payee information
                    transaction = await self._enhance_transaction(transaction)

                    # Apply category filter if specified
                    if categories and transaction.category not in categories:
                        continue

                    # Apply transaction type filter if specified
                    if (
                        transaction_types
                        and transaction.transaction_type not in transaction_types
                    ):
                        continue

                    transactions.append(transaction)

                except Exception as e:
                    logger.warning(f"Failed to parse transaction row: {e}")
                    continue

            logger.info(f"Retrieved {len(transactions)} transactions")
            return transactions

        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            raise RuntimeError(f"Failed to retrieve transactions: {e!s}") from e

    async def get_expense_summary(
        self, start_date: datetime, end_date: datetime, group_by: str = "category"
    ) -> dict[str, Any]:
        """
        Get expense summary grouped by category or payee.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            group_by: "category" or "payee"

        Returns:
            Dictionary with expense summary data
        """
        try:
            # Get all expense transactions (negative amounts, excluding transfers)
            transactions = await self.get_transactions(start_date, end_date)
            expenses = [
                t for t in transactions if t.is_expense() and not t.is_transfer()
            ]

            # Group expenses
            groups = {}
            total_expenses = Decimal("0")

            for expense in expenses:
                amount = abs(expense.amount)  # Make positive for display
                total_expenses += amount

                if group_by == "category":
                    group_key = expense.category or "Uncategorized"
                elif group_by == "payee":
                    group_key = expense.payee or "Unknown Payee"
                else:
                    group_key = "All Expenses"

                if group_key not in groups:
                    groups[group_key] = {
                        "total_amount": Decimal("0"),
                        "transaction_count": 0,
                        "transactions": [],
                    }

                groups[group_key]["total_amount"] += amount
                groups[group_key]["transaction_count"] += 1
                groups[group_key]["transactions"].append(expense)

            # Calculate percentages and create CategoryExpense objects
            category_expenses = []
            for group_name, data in groups.items():
                percentage = (
                    float(data["total_amount"] / total_expenses * 100)
                    if total_expenses > 0
                    else 0
                )
                avg_amount = (
                    data["total_amount"] / data["transaction_count"]
                    if data["transaction_count"] > 0
                    else Decimal("0")
                )

                category_expense = CategoryExpense(
                    category_name=group_name,
                    category_id=None,  # Could be enhanced later
                    total_amount=data["total_amount"],
                    transaction_count=data["transaction_count"],
                    average_amount=avg_amount,
                    percentage_of_total=percentage,
                )
                category_expenses.append(category_expense)

            # Sort by amount descending
            category_expenses.sort(key=lambda x: x.total_amount, reverse=True)

            return {
                "total_expenses": total_expenses,
                "category_breakdown": category_expenses,
                "analysis_period": DateRange(start_date=start_date, end_date=end_date),
                "currency": "USD",  # Default, could be enhanced
                "group_by": group_by,
            }

        except Exception as e:
            logger.error(f"Failed to get expense summary: {e}")
            raise RuntimeError(f"Failed to generate expense summary: {e!s}") from e

    async def get_income_vs_expense(
        self, start_date: datetime, end_date: datetime
    ) -> IncomeExpenseAnalysis:
        """
        Analyze income vs expenses for the given period.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis

        Returns:
            IncomeExpenseAnalysis object
        """
        try:
            # Get all transactions
            transactions = await self.get_transactions(start_date, end_date)

            # Separate income and expenses with smart transfer handling
            income_transactions = []
            expense_transactions = []

            for t in transactions:
                if t.is_expense() and not t.is_transfer():
                    # Regular expenses (excluding transfers)
                    expense_transactions.append(t)
                elif t.is_income():
                    if not t.is_transfer():
                        # Check if this is legitimate income or a misclassified transfer/loan
                        if self._is_legitimate_income(t):
                            income_transactions.append(t)
                    elif self._is_salary_related_transfer(t):
                        # Currency exchange transfers that represent salary conversion
                        # Convert to USD equivalent for consistent income calculation
                        income_transactions.append(t)
                        # Note: We may need to adjust for exchange rate to avoid double-counting

            # Calculate totals
            total_income = sum(t.amount for t in income_transactions)
            total_expenses = sum(
                abs(t.amount) for t in expense_transactions
            )  # Make positive
            net_savings = total_income - total_expenses
            savings_rate = (
                float(net_savings / total_income * 100) if total_income > 0 else 0
            )

            # Generate income breakdown
            await self.get_expense_summary(start_date, end_date, "category")
            # Note: This would need to be adapted for income transactions

            # Generate expense breakdown
            expense_summary = await self.get_expense_summary(
                start_date, end_date, "category"
            )

            return IncomeExpenseAnalysis(
                total_income=total_income,
                total_expenses=total_expenses,
                net_savings=net_savings,
                savings_rate=savings_rate,
                income_breakdown=[],  # Placeholder - would need income categorization
                expense_breakdown=expense_summary["category_breakdown"],
                analysis_period=DateRange(start_date=start_date, end_date=end_date),
                currency="USD",
                monthly_averages={},  # Placeholder - would need monthly breakdown
            )

        except Exception as e:
            logger.error(f"Failed to analyze income vs expenses: {e}")
            raise RuntimeError(f"Failed to analyze income vs expenses: {e!s}") from e

    async def _enhance_transaction(
        self, transaction: TransactionModel
    ) -> TransactionModel:
        """
        Enhance transaction with category and payee information.

        Args:
            transaction: Base transaction model

        Returns:
            Enhanced transaction model
        """
        try:
            # Get category from ZCATEGORYASSIGMENT table
            # MoneyWiz uses a separate table to link transactions to categories
            category_assignment_query = """
            SELECT ca.ZCATEGORY
            FROM ZCATEGORYASSIGMENT ca
            WHERE ca.ZTRANSACTION = ?
            LIMIT 1
            """

            category_assignment = await self.db_manager.execute_query(
                category_assignment_query, (int(transaction.id),)
            )

            if category_assignment:
                category_id = category_assignment[0]["ZCATEGORY"]

                # Get category name if not cached
                if category_id not in self._category_cache:
                    category_query = (
                        "SELECT ZNAME2 FROM ZSYNCOBJECT WHERE Z_ENT = 19 AND Z_PK = ?"
                    )
                    category_result = await self.db_manager.execute_query(
                        category_query, (category_id,)
                    )
                    if category_result and category_result[0]["ZNAME2"]:
                        self._category_cache[category_id] = category_result[0]["ZNAME2"]
                    else:
                        self._category_cache[category_id] = "Unknown Category"

                transaction.category = self._category_cache.get(
                    category_id, "Uncategorized"
                )
                transaction.category_id = category_id

                # Build category hierarchy
                await self._enhance_category_hierarchy(transaction)
            else:
                transaction.category = "Uncategorized"
                transaction.category_id = None

            # Get payee name if payee_id exists
            if transaction.payee_id and transaction.payee_id not in self._payee_cache:
                payee_query = (
                    "SELECT ZNAME FROM ZSYNCOBJECT WHERE Z_ENT = 28 AND Z_PK = ?"
                )
                payee_result = await self.db_manager.execute_query(
                    payee_query, (transaction.payee_id,)
                )
                if payee_result:
                    self._payee_cache[transaction.payee_id] = payee_result[0]["ZNAME"]
                else:
                    self._payee_cache[transaction.payee_id] = "Unknown Payee"

            if transaction.payee_id:
                transaction.payee = self._payee_cache.get(
                    transaction.payee_id, "Unknown Payee"
                )

            # Get account currency if not cached
            if transaction.account_id not in self._account_currency_cache:
                account_query = """
                SELECT ZCURRENCYNAME FROM ZSYNCOBJECT
                WHERE Z_ENT BETWEEN 10 AND 16 AND Z_PK = ?
                """
                account_result = await self.db_manager.execute_query(
                    account_query, (transaction.account_id,)
                )
                if account_result:
                    self._account_currency_cache[transaction.account_id] = (
                        account_result[0]["ZCURRENCYNAME"]
                    )
                else:
                    self._account_currency_cache[transaction.account_id] = "USD"

            transaction.currency = self._account_currency_cache.get(
                transaction.account_id, "USD"
            )

            # Get tags for this transaction
            await self._enhance_transaction_with_tags(transaction)

            return transaction

        except Exception as e:
            logger.warning(f"Failed to enhance transaction {transaction.id}: {e}")
            return transaction

    def _is_salary_related_transfer(self, transaction: TransactionModel) -> bool:
        """
        Determine if a transfer represents salary currency conversion.

        This method identifies transfers that are part of salary processing,
        such as USD salary converted to local currency (CRC).

        Args:
            transaction: Transfer transaction to evaluate

        Returns:
            True if this transfer represents salary conversion
        """
        if not transaction.is_transfer():
            return False

        # Strategy 1: Check if this is a currency conversion transfer
        # (has original amount/currency different from current)
        if (
            transaction.original_amount
            and transaction.original_currency
            and transaction.original_currency != transaction.currency
        ):
            return True

        # Strategy 2: Check for salary-related keywords in description
        if transaction.description:
            salary_keywords = ["salary", "salar", "payroll", "income", "wage"]
            desc_lower = transaction.description.lower()
            if any(keyword in desc_lower for keyword in salary_keywords):
                return True

        # Strategy 3: Check if the transfer amount matches recent salary deposits
        # (within same day/week and similar amount)
        # This would require more complex logic to match salary patterns

        # For now, be conservative and only include obvious currency conversions
        return False

    def _is_legitimate_income(self, transaction: TransactionModel) -> bool:
        """
        Determine if a positive amount transaction represents legitimate income.

        This method filters out large deposits that are likely transfers, loans,
        or other non-income movements misclassified as income.

        Args:
            transaction: Income transaction to evaluate

        Returns:
            True if this represents legitimate income
        """
        if not transaction.is_income():
            return False

        amount_usd = float(transaction.amount)

        # Convert CRC to USD for comparison (approximate rate 1 USD = 500 CRC)
        if transaction.currency == "CRC":
            amount_usd = amount_usd / 500

        # Strategy 1: Check if category is a known income category
        income_categories = {
            "salary",
            "interest earned",
            "dividend payment",
            "rental",
            "crypto",
            "cashback",
            "social welfare",
            "rendimientos",
            "sales",
            "outsourcing",
            "interest",
            "dividend",
            "investment",
            "income",
            "bonus",
            "freelance",
            "commission",
            "royalty",
            "pension",
            "allowance",
            "grant",
            "subsidy",
        }

        if transaction.category:
            category_lower = transaction.category.lower()
            if any(income_cat in category_lower for income_cat in income_categories):
                # This is clearly an income category, allow larger amounts
                if amount_usd > 50000:  # Still filter extremely large amounts
                    return False
                return True

        # Strategy 1b: Include other categorized income (user has explicitly categorized it)
        if transaction.category and transaction.category not in ["Uncategorized", None]:
            # But be suspicious of very large categorized amounts
            if amount_usd > 10000:  # Lower threshold for non-obvious income categories
                return False
            return True

        # Strategy 2: Filter out large uncategorized deposits (likely transfers/loans)
        if amount_usd > 1000:  # >$1K USD uncategorized is suspicious
            return False

        # Strategy 3: Filter out transfer-like descriptions
        if transaction.description:
            transfer_keywords = [
                "transfer",
                "pago",
                "sbd",
                "loan",
                "prestamo",
                "adjustment",
                "ajuste",
                "movimiento",
                "deposito",
            ]
            desc_lower = transaction.description.lower()
            if any(keyword in desc_lower for keyword in transfer_keywords):
                return False

        # Strategy 4: Accept small amounts and typical income patterns
        # Small amounts (<$1K USD) are likely legitimate income
        return True

    async def _enhance_transaction_with_tags(
        self, transaction: TransactionModel
    ) -> None:
        """
        Enhance transaction with tag information from Z_36TAGS table.

        Args:
            transaction: Transaction to enhance with tags
        """
        try:
            # Get tag IDs for this transaction
            tag_query = """
            SELECT Z_35TAGS as tag_id
            FROM Z_36TAGS
            WHERE Z_36TRANSACTIONS = ?
            """

            tag_results = await self.db_manager.execute_query(
                tag_query, (int(transaction.id),)
            )

            if tag_results:
                tag_names = []
                for tag_result in tag_results:
                    tag_id = tag_result["tag_id"]

                    # Get tag name if not cached
                    if tag_id not in self._tag_cache:
                        # Try different fields for tag names - investigate all available fields
                        tag_name_query = """
                        SELECT ZNAME, ZNAME2, ZTITLE, ZLABEL, ZDESC, ZDESC2, ZVALUE
                        FROM ZSYNCOBJECT
                        WHERE Z_ENT = 35 AND Z_PK = ?
                        """
                        tag_name_result = await self.db_manager.execute_query(
                            tag_name_query, (tag_id,)
                        )

                        if tag_name_result:
                            # Try different name fields in order of preference
                            tag_row = tag_name_result[0]
                            tag_name = (
                                tag_row.get("ZNAME2")
                                or tag_row.get("ZNAME")
                                or tag_row.get("ZTITLE")
                                or tag_row.get("ZLABEL")
                                or tag_row.get("ZDESC2")
                                or tag_row.get("ZDESC")
                                or tag_row.get("ZVALUE")
                                or f"Tag_{tag_id}"
                            )
                            self._tag_cache[tag_id] = tag_name

                            # Log what fields we found for debugging
                            logger.debug(f"Tag {tag_id} fields: {dict(tag_row)}")
                        else:
                            self._tag_cache[tag_id] = f"Tag_{tag_id}"

                    tag_name = self._tag_cache.get(tag_id, f"Tag_{tag_id}")
                    if tag_name and tag_name != "NULL":
                        tag_names.append(tag_name)

                transaction.tags = tag_names

        except Exception as e:
            logger.warning(
                f"Failed to enhance transaction {transaction.id} with tags: {e}"
            )
            transaction.tags = []

    async def _enhance_category_hierarchy(self, transaction: TransactionModel) -> None:
        """
        Build full category hierarchy path for transaction.

        Resolves parent-child category relationships to create paths like:
        "Food & Dining ▶ Groceries"

        Args:
            transaction: Transaction to enhance with category hierarchy
        """
        if not transaction.category_id:
            return

        try:
            # Build hierarchy by traversing parent categories
            hierarchy = []
            current_id = transaction.category_id
            visited_ids = set()  # Prevent infinite loops

            while current_id and current_id not in visited_ids:
                visited_ids.add(current_id)

                # Get category name and parent category
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
                        )  # Add to beginning for correct order

                    current_id = parent_id
                else:
                    break

            # Set hierarchy information
            if len(hierarchy) > 1:
                # Multi-level hierarchy
                transaction.parent_category = hierarchy[0]
                transaction.category_path = " ▶ ".join(hierarchy)
                transaction.category_hierarchy = hierarchy

                # Update main category to be the leaf (most specific)
                transaction.category = hierarchy[-1]

                # Cache parent category info if we found it
                if len(hierarchy) >= 2:
                    # Get parent category ID for caching
                    parent_query = """
                    SELECT Z_PK FROM ZSYNCOBJECT
                    WHERE Z_ENT = 19 AND ZNAME2 = ?
                    """
                    parent_result = await self.db_manager.execute_query(
                        parent_query, (hierarchy[0],)
                    )
                    if parent_result:
                        transaction.parent_category_id = parent_result[0]["Z_PK"]
            elif len(hierarchy) == 1:
                # Single-level category (no parent)
                transaction.category_hierarchy = hierarchy
                transaction.category_path = hierarchy[0]

            logger.debug(
                f"Enhanced transaction {transaction.id} with category hierarchy: {transaction.category_path}"
            )

        except Exception as e:
            logger.warning(
                f"Failed to build category hierarchy for transaction {transaction.id}: {e}"
            )
            # Keep basic category info if hierarchy fails
