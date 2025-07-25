"""Transaction service for MoneyWiz MCP Server."""

from datetime import datetime
from decimal import Decimal
import logging

from typing_extensions import TypedDict

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
from moneywiz_mcp_server.services.category_classification_service import (
    CategoryClassificationService,
    CategoryType,
)
from moneywiz_mcp_server.utils.date_utils import datetime_to_core_data_timestamp

logger = logging.getLogger(__name__)


class ExpenseGroupData(TypedDict):
    """TypedDict for expense group aggregation data."""

    total_amount: Decimal
    transaction_count: int
    transactions: list["TransactionModel"]


class ExpenseSummaryResult(TypedDict):
    """TypedDict for expense summary return data."""

    total_expenses_by_currency: dict[str, Decimal]
    category_breakdown: list[CategoryExpense]
    analysis_period: DateRange
    group_by: str


class TransactionService:
    """Service for transaction operations and analysis."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._category_cache: dict[int, str] = {}
        self._payee_cache: dict[int, str] = {}
        self._account_currency_cache: dict[int, str] = {}
        self._tag_cache: dict[int, str] = {}  # Cache for tag names

        # Initialize category classification service
        self.category_classifier = CategoryClassificationService(db_manager)

    async def get_transactions(
        self,
        start_date: datetime,
        end_date: datetime,
        account_ids: list[str] | None = None,
        categories: list[str] | None = None,
        transaction_types: list[TransactionType] | None = None,
        limit: int | None = None,
    ) -> list[TransactionModel]:
        """
        Get transactions with filtering options.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            account_ids: Optional list of external account IDs (UUID strings) to filter
            categories: Optional list of category names to filter
            transaction_types: Optional list of transaction types to filter
            limit: Optional limit on number of results

        Returns:
            List of TransactionModel objects
        """
        try:
            # Convert external account IDs (UUID strings) to internal database IDs (integers)
            internal_account_ids: list[int] | None = None
            if account_ids:
                internal_account_ids = (
                    await self._convert_external_account_ids_to_internal(account_ids)
                )
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
            if internal_account_ids:
                account_placeholders = ",".join("?" for _ in internal_account_ids)
                where_conditions.append(f"ZACCOUNT2 IN ({account_placeholders})")  # nosec: B608 - Safe placeholder substitution
                params.extend(internal_account_ids)

            # Build final query using safe parameter substitution
            # nosec: B608 - Safe use of .format() with parameterized WHERE conditions
            base_query = """
            SELECT * FROM ZSYNCOBJECT
            WHERE {}
            ORDER BY ZDATE1 DESC
            """.format(" AND ".join(where_conditions))  # nosec

            # Apply limit at database level only if no category filtering is needed
            # When categories are specified, we need to get more data to filter properly
            if limit and not categories:
                query = base_query + " LIMIT ?"
                params.append(limit)
            else:
                query = base_query

            logger.info(f"🔍 Executing transaction query with {len(params)} parameters")
            logger.info(
                f"📅 Date range timestamps: {start_timestamp} to {end_timestamp}"
            )
            logger.info(f"🔢 Query entities: {transaction_entities}")
            logger.debug(f"SQL Query: {query}")
            logger.debug(f"Query params: {params}")

            # Execute query (convert params list to tuple for database manager)
            rows = await self.db_manager.execute_query(query, tuple(params))
            logger.info(f"📊 Query returned {len(rows)} rows")

            # Convert to TransactionModel objects
            transactions: list[TransactionModel] = []
            category_filtered_count = 0
            for row in rows:
                try:
                    transaction = TransactionModel.from_raw_data(row)

                    # Enhance with category and payee information
                    transaction = await self._enhance_transaction(transaction)

                    # Apply category filter if specified
                    if categories:
                        # Check if any category in the hierarchy matches the filter
                        category_matches = False

                        # Check leaf category
                        if transaction.category in categories or (
                            transaction.parent_category
                            and transaction.parent_category in categories
                        ):
                            category_matches = True

                        # Check all categories in hierarchy
                        elif transaction.category_hierarchy:
                            for cat in transaction.category_hierarchy:
                                if cat in categories:
                                    category_matches = True
                                    break

                        if not category_matches:
                            category_filtered_count += 1
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

            # Apply limit after filtering when categories were specified
            if categories and limit and len(transactions) > limit:
                logger.info(f"🔢 Applying limit of {limit} after category filtering")
                transactions = transactions[:limit]

            logger.info(f"Retrieved {len(transactions)} transactions")
            if categories:
                logger.info(
                    f"📊 Category filtering results: {category_filtered_count} transactions filtered out"
                )
            return transactions

        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            raise RuntimeError(f"Failed to retrieve transactions: {e!s}") from e

    async def get_expense_summary(
        self, start_date: datetime, end_date: datetime, group_by: str = "category"
    ) -> ExpenseSummaryResult:
        """
        Get expense summary grouped by category or payee with multi-currency support.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            group_by: "category" or "payee"

        Returns:
            Dictionary with multi-currency expense summary data
        """
        try:
            # Get all expense transactions (negative amounts, excluding transfers)
            transactions = await self.get_transactions(start_date, end_date)
            expenses = [
                t for t in transactions if t.is_expense() and not t.is_transfer()
            ]

            # Group expenses by category/payee AND currency
            # Data structure maps category to currency to expense data
            groups: dict[str, dict[str, ExpenseGroupData]] = {}
            total_expenses_by_currency: dict[str, Decimal] = {}

            for expense in expenses:
                amount = abs(expense.amount)  # Make positive for display
                currency = expense.currency

                # Track total expenses by currency
                if currency not in total_expenses_by_currency:
                    total_expenses_by_currency[currency] = Decimal("0")
                total_expenses_by_currency[currency] += amount

                # Determine group key
                if group_by == "category":
                    group_key = expense.category or "Uncategorized"
                elif group_by == "payee":
                    group_key = expense.payee or "Unknown Payee"
                else:
                    group_key = "All Expenses"

                # Initialize nested structure if needed
                if group_key not in groups:
                    groups[group_key] = {}
                if currency not in groups[group_key]:
                    groups[group_key][currency] = ExpenseGroupData(
                        total_amount=Decimal("0"),
                        transaction_count=0,
                        transactions=[],
                    )

                # Add to currency-specific group
                groups[group_key][currency]["total_amount"] += amount
                groups[group_key][currency]["transaction_count"] += 1
                groups[group_key][currency]["transactions"].append(expense)

            # Create multi-currency CategoryExpense objects
            category_expenses: list[CategoryExpense] = []
            for group_name, currency_groups in groups.items():
                # Aggregate data across currencies for this category
                amounts_by_currency = {}
                transaction_counts_by_currency = {}
                average_amounts_by_currency = {}
                percentage_within_currency = {}

                # Calculate totals across all currencies for compatibility
                total_amount_all_currencies = Decimal("0")
                total_count_all_currencies = 0

                for currency, data in currency_groups.items():
                    amounts_by_currency[currency] = data["total_amount"]
                    transaction_counts_by_currency[currency] = data["transaction_count"]
                    average_amounts_by_currency[currency] = (
                        data["total_amount"] / data["transaction_count"]
                        if data["transaction_count"] > 0
                        else Decimal("0")
                    )
                    # Calculate percentage within this currency
                    currency_total = total_expenses_by_currency[currency]
                    percentage_within_currency[currency] = (
                        data["total_amount"] / currency_total * Decimal("100")
                        if currency_total > 0
                        else Decimal("0")
                    )

                    # Sum up for backward compatibility
                    total_amount_all_currencies += data["total_amount"]
                    total_count_all_currencies += data["transaction_count"]

                # Calculate overall percentage across all currencies
                total_all_expenses = sum(total_expenses_by_currency.values())
                overall_percentage = (
                    total_amount_all_currencies / total_all_expenses * Decimal("100")
                    if total_all_expenses > 0
                    else Decimal("0")
                )

                # Create CategoryExpense object for backward compatibility
                category_expense = CategoryExpense(
                    category_name=group_name,
                    category_id=None,  # Could be enhanced later
                    total_amount=total_amount_all_currencies,
                    transaction_count=total_count_all_currencies,
                    average_amount=(
                        total_amount_all_currencies / total_count_all_currencies
                        if total_count_all_currencies > 0
                        else Decimal("0")
                    ),
                    percentage_of_total=overall_percentage,
                )

                # Add multi-currency data as additional attributes for API responses
                category_expense.amounts_by_currency = amounts_by_currency
                category_expense.transaction_counts_by_currency = (
                    transaction_counts_by_currency
                )
                category_expense.average_amounts_by_currency = (
                    average_amounts_by_currency
                )
                category_expense.percentage_within_currency = percentage_within_currency

                category_expenses.append(category_expense)

            # Sort by total amount across all currencies
            def get_total_amount_for_sorting(category: CategoryExpense) -> float:
                return float(category.total_amount)

            category_expenses.sort(key=get_total_amount_for_sorting, reverse=True)

            return {
                "total_expenses_by_currency": total_expenses_by_currency,
                "category_breakdown": category_expenses,
                "analysis_period": DateRange(start_date=start_date, end_date=end_date),
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
            income_transactions: list[TransactionModel] = []
            expense_transactions: list[TransactionModel] = []

            for t in transactions:
                if t.is_expense() and not t.is_transfer():
                    # Regular expenses (excluding transfers)
                    expense_transactions.append(t)
                elif t.is_income():
                    if not t.is_transfer():
                        # Check if this is legitimate income or a misclassified transfer/loan
                        if await self._is_legitimate_income(t):
                            income_transactions.append(t)
                    elif self._is_salary_related_transfer(t):
                        # Currency exchange transfers that represent salary conversion
                        # Convert to USD equivalent for consistent income calculation
                        income_transactions.append(t)
                        # Note: We may need to adjust for exchange rate to avoid double-counting

            # Calculate totals using CurrencyAmounts for type safety
            from moneywiz_mcp_server.models.currency_types import CurrencyAmounts

            # Accumulate income and expenses using CurrencyAmounts
            income_amounts = {}
            expense_amounts = {}

            # Group income by currency
            for t in income_transactions:
                currency = t.currency
                if currency not in income_amounts:
                    income_amounts[currency] = Decimal("0")
                income_amounts[currency] += t.amount

            # Group expenses by currency
            for t in expense_transactions:
                currency = t.currency
                if currency not in expense_amounts:
                    expense_amounts[currency] = Decimal("0")
                expense_amounts[currency] += abs(t.amount)  # Make positive

            # Create CurrencyAmounts objects
            total_income = CurrencyAmounts(income_amounts)
            total_expenses = CurrencyAmounts(expense_amounts)

            # Calculate net savings using CurrencyAmounts arithmetic
            net_savings = total_income - total_expenses

            # Calculate savings rates using CurrencyAmounts method
            savings_rate_by_currency = net_savings.calculate_rates(total_income)

            # Get primary currency and currencies list
            activity_amounts = total_income + total_expenses
            primary_currency = activity_amounts.primary_currency()
            currencies_found = activity_amounts.currencies()

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
                savings_rate=savings_rate_by_currency,
                income_breakdown=[],  # Placeholder - would need income categorization
                expense_breakdown=expense_summary["category_breakdown"],
                analysis_period=DateRange(start_date=start_date, end_date=end_date),
                currencies_found=currencies_found,
                primary_currency=primary_currency,
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

            # Get tags for this transaction (disabled due to schema changes)
            transaction.tags = []  # Set empty tags to avoid errors

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

    async def _is_legitimate_income(self, transaction: TransactionModel) -> bool:
        """
        Determine if a positive amount transaction represents legitimate income.

        Uses MoneyWiz's category hierarchy to intelligently classify transactions
        without relying on hardcoded patterns or personal information.

        Args:
            transaction: Income transaction to evaluate

        Returns:
            True if this represents legitimate income
        """
        if not transaction.is_income():
            return False

        # Debug logging for income detection
        logger.debug(
            "Income check for transaction %s: amount=%s, category='%s', currency='%s'",
            transaction.id,
            transaction.amount,
            transaction.category,
            transaction.currency,
        )

        # Strategy 1: Use category-based classification (primary method)
        if transaction.category_id:
            try:
                is_income = await self.category_classifier.is_income_category(
                    transaction.category_id
                )
                if is_income:
                    logger.debug(
                        "Income accepted for transaction %s: category hierarchy classification",
                        transaction.id,
                    )
                    return True

                # Check if it's explicitly classified as a transfer or adjustment
                is_transfer = await self.category_classifier.is_transfer_category(
                    transaction.category_id
                )
                if is_transfer:
                    logger.debug(
                        "Income rejected for transaction %s: classified as transfer",
                        transaction.id,
                    )
                    return False
            except Exception as e:
                logger.warning(
                    "Category classification failed for transaction %s: %s",
                    transaction.id,
                    e,
                )

        # Strategy 2: Transaction type-based classification
        # DEPOSIT transactions with income categories should be treated as income
        if (
            transaction.transaction_type == TransactionType.DEPOSIT
            and transaction.category
            and transaction.category not in ["Uncategorized", None, ""]
        ):
            # User has categorized this deposit, likely legitimate income
            logger.debug(
                "Income accepted for transaction %s: categorized deposit",
                transaction.id,
            )
            return True

        # Strategy 3: Filter out obvious transfers and adjustments by transaction type
        if transaction.transaction_type in [
            TransactionType.TRANSFER_IN,
            TransactionType.TRANSFER_OUT,
        ]:
            # This is a transfer, not income
            logger.debug(
                "Income rejected for transaction %s: transfer type", transaction.id
            )
            return False

        if transaction.transaction_type in [
            TransactionType.RECONCILE,
            TransactionType.ADJUST_BALANCE,
        ]:
            # This is a reconciliation/adjustment, not income
            logger.debug(
                "Income rejected for transaction %s: reconciliation/adjustment type",
                transaction.id,
            )
            return False

        # Strategy 4: Smart amount-based filtering with currency awareness
        amount_usd = float(transaction.amount)

        # Convert non-USD amounts for comparison
        if transaction.currency == "CRC":
            amount_usd = amount_usd / 500  # Approximate CRC to USD rate
        elif transaction.currency == "EUR":
            amount_usd = amount_usd * 1.1  # Approximate EUR to USD rate

        # Filter extremely large amounts that are likely misclassified transfers
        if amount_usd > 100000:  # >$100K is suspicious regardless of category
            logger.debug(
                "Income rejected for transaction %s: extremely large amount ($%.2f)",
                transaction.id,
                amount_usd,
            )
            return False

        # Strategy 5: Description-based filtering (conservative)
        if transaction.description:
            desc_lower = transaction.description.lower()

            # Filter out obvious non-income descriptions
            non_income_keywords = [
                "loan",
                "prestamo",
                "credit",
                "credito",
                "adjustment",
                "ajuste",
                "correction",
                "corrección",
                "opening balance",
                "balance inicial",
                "inicial",
            ]

            if any(keyword in desc_lower for keyword in non_income_keywords):
                logger.debug(
                    "Income rejected for transaction %s: non-income description pattern",
                    transaction.id,
                )
                return False

        # Strategy 6: Default acceptance for categorized positive amounts
        if transaction.category and transaction.category not in [
            "Uncategorized",
            None,
            "",
        ]:
            logger.debug(
                "Income accepted for transaction %s: categorized positive amount",
                transaction.id,
            )
            return True

        # Strategy 7: Conservative acceptance for small uncategorized amounts
        if amount_usd <= 1000:  # Small amounts are likely legitimate
            logger.debug(
                "Income accepted for transaction %s: small amount", transaction.id
            )
            return True

        # Default: reject large uncategorized deposits
        logger.debug(
            "Income rejected for transaction %s: large uncategorized amount",
            transaction.id,
        )
        return False

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
                tag_names: list[str] = []
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
            hierarchy: list[str] = []
            current_id: int | None = transaction.category_id
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

                    current_id = parent_id if isinstance(parent_id, int) else None
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

    async def _convert_external_account_ids_to_internal(
        self, external_account_ids: list[str]
    ) -> list[int]:
        """
        Convert external account IDs (UUID strings or stringified integers) to internal database IDs.

        MoneyWiz uses two ID systems:
        1. External IDs (ZGID): UUID strings like 'A6CA789E-39DA-4FF1-A8DC-2DDA96B6E22B-1585-0000004B3F183772'
        2. Internal IDs (Z_PK): Integer primary keys used in database relationships like ZACCOUNT2

        Args:
            external_account_ids: List of external account IDs (UUID strings)

        Returns:
            List of internal account IDs (integers) for database queries

        Raises:
            ValueError: If any account ID cannot be found or converted
        """
        internal_ids: list[int] = []

        for external_id in external_account_ids:
            try:
                # Try to find account by ZGID (UUID string)
                zgid_query = """
                SELECT Z_PK FROM ZSYNCOBJECT
                WHERE Z_ENT BETWEEN 10 AND 16 AND ZGID = ?
                """
                result = await self.db_manager.execute_query(zgid_query, (external_id,))

                if result:
                    internal_ids.append(result[0]["Z_PK"])
                    logger.debug(
                        f"Converted external account ID {external_id} to internal ID {result[0]['Z_PK']}"
                    )
                    continue

                # Fallback: Try to parse as stringified integer (old format compatibility)
                try:
                    potential_internal_id = int(external_id)
                    # Verify this internal ID exists
                    internal_query = """
                    SELECT Z_PK FROM ZSYNCOBJECT
                    WHERE Z_ENT BETWEEN 10 AND 16 AND Z_PK = ?
                    """
                    verify_result = await self.db_manager.execute_query(
                        internal_query, (potential_internal_id,)
                    )

                    if verify_result:
                        internal_ids.append(potential_internal_id)
                        logger.debug(
                            f"Used stringified internal account ID {external_id} as internal ID {potential_internal_id}"
                        )
                        continue
                except ValueError:
                    # Not a valid integer, continue to error
                    pass

                # Neither ZGID lookup nor integer parsing worked
                raise ValueError(
                    f"Account ID '{external_id}' not found in MoneyWiz database"
                )

            except Exception as e:
                logger.error(f"Failed to convert account ID '{external_id}': {e}")
                raise ValueError(f"Invalid account ID '{external_id}': {e}") from e

        return internal_ids
