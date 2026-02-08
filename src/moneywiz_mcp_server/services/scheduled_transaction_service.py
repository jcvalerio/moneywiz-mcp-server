"""Service for scheduled transaction operations and occurrence tracking."""

from datetime import datetime, timedelta
from decimal import Decimal
import logging
from typing import Any

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.currency_types import CurrencyAmounts
from moneywiz_mcp_server.models.scheduled_transaction import (
    CommitmentBreakdown,
    RecurrenceEndCondition,
    RecurrencePattern,
    SalaryBreakdownResponse,
    ScheduledTransactionModel,
    WeekendHandling,
)
from moneywiz_mcp_server.models.transaction import TransactionType
from moneywiz_mcp_server.utils.date_utils import datetime_to_core_data_timestamp

logger = logging.getLogger(__name__)


class ScheduledTransactionService:
    """Service for scheduled transaction operations with occurrence tracking."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._category_cache: dict[int, str] = {}
        self._payee_cache: dict[int, str] = {}
        self._account_cache: dict[int, str] = {}

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

            # Entity 33: Scheduled Transfer transactions (between accounts)
            # Entity 34: Regular scheduled transactions (to payees)
            scheduled_entities = [33, 34]

            for entity_type in scheduled_entities:
                # Query for active scheduled transactions
                query = """
                    SELECT * FROM ZSYNCOBJECT
                    WHERE Z_ENT = ? AND ZISREPEATABLE1 = 1
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
                            record, entity_type
                        )

                        # Apply filters
                        if scheduled_transaction and await self._matches_filters(
                            scheduled_transaction,
                            account_ids,
                            categories,
                            commitment_types,
                        ):
                            scheduled_transactions.append(scheduled_transaction)

                    except Exception as e:  # noqa: PERF203
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
        self, record: dict[str, Any], entity_type: int
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
            next_execution_date = self._core_data_timestamp_to_datetime(
                next_date_timestamp
            )

            # Get creation date
            created_timestamp = record.get("ZCREATIONDATE1") or record.get(
                "ZOBJECTCREATIONDATE"
            )
            created_date = (
                self._core_data_timestamp_to_datetime(created_timestamp)
                if created_timestamp
                else datetime.now()
            )

            # Get account, category, payee info based on entity type
            if entity_type == 33:  # Transfer transactions
                account_id = str(record.get("ZACCOUNT1", ""))
                category = "Transfer"
                payee = "Transfer to Account"
            else:  # Entity 34 - Regular transactions
                account_id = str(record.get("ZACCOUNT1", ""))
                category = await self._get_category_name_for_scheduled(record)
                payee = await self._get_payee_name(record.get("ZPAYEE1"))

            # Determine recurrence pattern from ZDURATIONUNITS1
            recurrence_pattern = self._infer_recurrence_pattern_from_duration(record)

            # Calculate occurrence data from actual fields
            executes_count = record.get("ZEXECUTESCOUNT", 0)
            total_occurrences = (
                None  # MoneyWiz doesn't seem to use fixed total occurrences
            )
            remaining_occurrences = None

            # Determine end condition - MoneyWiz scheduled transactions seem to run indefinitely
            end_condition = RecurrenceEndCondition.NEVER

            # Generate upcoming dates
            upcoming_dates = await self._generate_upcoming_dates(
                next_execution_date, recurrence_pattern, None, 6
            )

            # Get description
            description = record.get("ZDESC1") or f"Scheduled {category}"

            # Create the model
            scheduled_transaction = ScheduledTransactionModel(
                id=str(record.get("Z_PK", "")),
                description=description,
                amount=Decimal(str(amount)),
                currency=record.get("ZCURRENCYNAME3", "USD"),
                account_id=account_id,
                category=category or "Uncategorized",
                payee=payee or "Unknown",
                transaction_type=self._infer_transaction_type(amount),
                recurrence_pattern=recurrence_pattern,
                recurrence_interval=record.get("ZDURATION1", 1),
                next_execution_date=next_execution_date,
                weekend_handling=self._infer_weekend_handling(record),
                end_condition=end_condition,
                total_occurrences=total_occurrences,
                completed_occurrences=executes_count,
                remaining_occurrences=remaining_occurrences,
                final_execution_date=None,  # No fixed end date for most MoneyWiz schedules
                upcoming_dates=upcoming_dates,
                is_active=record.get("ZDISABLEEXECUTION", 0) == 0,
                created_date=created_date,
                last_executed_date=None,  # Would need to parse from ZEXECUTEDTRANSACTIONSDATESARRAY
                entity_type=entity_type,
                database_id=record.get("Z_PK", 0),
            )

            return scheduled_transaction

        except Exception as e:
            logger.error(f"Failed to convert record to model: {e}")
            return None

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

    def _core_data_timestamp_to_datetime(self, timestamp: float) -> datetime:
        """Convert Core Data timestamp to Python datetime."""
        # Core Data reference date: January 1, 2001, 00:00:00 UTC
        core_data_epoch = datetime(2001, 1, 1)
        return core_data_epoch + timedelta(seconds=timestamp)

    def _infer_recurrence_pattern_from_duration(
        self, record: dict[str, Any]
    ) -> RecurrencePattern:
        """Infer recurrence pattern from ZDURATIONUNITS1 field."""
        # Based on observed data:
        # ZDURATIONUNITS1 = 4 appears to be yearly
        # ZDURATIONUNITS1 = 8 appears to be monthly
        duration_units = record.get("ZDURATIONUNITS1", 8)

        patterns = {
            1: RecurrencePattern.DAILY,
            2: RecurrencePattern.WEEKLY,
            4: RecurrencePattern.YEARLY,
            8: RecurrencePattern.MONTHLY,
        }
        # Default to monthly for unknown patterns
        return patterns.get(duration_units, RecurrencePattern.MONTHLY)

    def _infer_weekend_handling(self, record: dict[str, Any]) -> WeekendHandling:
        """Infer weekend handling from ZWEEKENDSHANDLER field."""
        weekend_handler = record.get("ZWEEKENDSHANDLER", 2)

        handlers = {
            0: WeekendHandling.SAME_DAY,
            1: WeekendHandling.PREVIOUS_WEEKDAY,
            2: WeekendHandling.NEXT_WEEKDAY,
        }
        return handlers.get(weekend_handler, WeekendHandling.SAME_DAY)

    async def _get_category_name_for_scheduled(
        self, record: dict[str, Any]
    ) -> str | None:
        """Get category name for scheduled transactions."""
        # For scheduled transactions, category might not be directly linked
        # This would need investigation into how MoneyWiz stores categories for scheduled transactions
        # For now, return a default based on transaction type
        if record.get("ZPAYEE1"):
            return "Bills & Utilities"
        else:
            return "Transfer"

    def _infer_transaction_type(self, amount: float) -> TransactionType:
        """Infer transaction type from amount."""
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
    ) -> list[datetime]:
        """Generate list of upcoming execution dates."""
        upcoming_dates = []
        current_date = next_date
        max_dates = remaining_occurrences or (months_ahead * 12)  # Reasonable limit

        for i in range(min(max_dates, 20)):  # Limit to 20 dates for performance
            if current_date > datetime.now() + timedelta(days=months_ahead * 30):
                break

            upcoming_dates.append(current_date)

            # Calculate next date based on pattern
            if pattern == RecurrencePattern.DAILY:
                current_date += timedelta(days=1)
            elif pattern == RecurrencePattern.WEEKLY:
                current_date += timedelta(weeks=1)
            elif pattern == RecurrencePattern.MONTHLY:
                # Add one month (approximate)
                if current_date.month == 12:
                    current_date = current_date.replace(
                        year=current_date.year + 1, month=1
                    )
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            elif pattern == RecurrencePattern.YEARLY:
                current_date = current_date.replace(year=current_date.year + 1)

            if remaining_occurrences and i + 1 >= remaining_occurrences:
                break

        return upcoming_dates

    async def _get_category_name(self, category_id: int | None) -> str | None:
        """Get category name from cache or database."""
        if not category_id:
            return None

        if category_id in self._category_cache:
            return self._category_cache[category_id]

        try:
            query = "SELECT ZNAME2 FROM ZSYNCOBJECT WHERE Z_ENT = 19 AND Z_PK = ?"
            result = await self.db_manager.execute_query(query, (category_id,))
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
            query = "SELECT ZNAME FROM ZSYNCOBJECT WHERE Z_ENT = 28 AND Z_PK = ?"
            result = await self.db_manager.execute_query(query, (payee_id,))
            if result:
                payee_name: str = result[0].get("ZNAME", "Unknown")
                self._payee_cache[payee_id] = payee_name
                return payee_name
        except Exception as e:
            logger.warning(f"Failed to get payee name for {payee_id}: {e}")

        return None

    async def calculate_salary_breakdown(
        self,
        next_salary_date: datetime,
        salary_amount: Decimal | None = None,
        planning_horizon_months: int = 3,
    ) -> dict[str, Any]:
        """
        Calculate salary breakdown showing how salary covers upcoming commitments.

        Args:
            next_salary_date: Date of next salary payment
            salary_amount: Optional salary amount (estimated if not provided)
            planning_horizon_months: How far ahead to analyze (default 3 months)

        Returns:
            Dictionary with salary breakdown analysis
        """
        try:
            logger.info(f"💰 Calculating salary breakdown for {next_salary_date}")

            # Get all scheduled transactions
            scheduled_transactions = await self.get_scheduled_transactions()

            # Calculate period end date
            period_end = next_salary_date + timedelta(days=planning_horizon_months * 30)

            # Categorize commitments by type
            finite_commitments = []
            infinite_commitments = []
            ending_soon_commitments = []

            total_commitments = Decimal("0")
            commitments_by_currency: dict[str, Decimal] = {}

            for transaction in scheduled_transactions:
                # Count payments in the period
                payments_in_period = 0
                total_impact = Decimal("0")

                for upcoming_date in transaction.upcoming_dates:
                    if next_salary_date <= upcoming_date <= period_end:
                        payments_in_period += 1
                        total_impact += abs(transaction.amount)

                if payments_in_period == 0:
                    continue  # No payments in this period

                # Create commitment breakdown
                commitment = CommitmentBreakdown(
                    description=transaction.description,
                    amount=abs(transaction.amount),
                    currency=transaction.currency,
                    category=transaction.category,
                    next_date=transaction.next_execution_date,
                    remaining_payments=transaction.remaining_occurrences,
                    final_payment_date=transaction.final_execution_date,
                    payments_in_period=payments_in_period,
                    total_impact_in_period=total_impact,
                    commitment_type=transaction.commitment_type,
                    urgency_level=transaction.urgency_level,
                )

                # Categorize by commitment type
                if transaction.commitment_type == "ending_soon":
                    ending_soon_commitments.append(commitment)
                elif transaction.commitment_type == "finite":
                    finite_commitments.append(commitment)
                else:
                    infinite_commitments.append(commitment)

                # Add to totals
                total_commitments += total_impact
                currency = transaction.currency
                if currency not in commitments_by_currency:
                    commitments_by_currency[currency] = Decimal("0")
                commitments_by_currency[currency] += total_impact

            # Estimate salary if not provided
            if salary_amount is None:
                # Simple estimation based on historical income data
                salary_amount = await self._estimate_salary_amount()

            # Assume salary is in primary currency (USD for now)
            primary_currency = "USD"
            salary_by_currency = {primary_currency: salary_amount}

            # Calculate remaining amounts
            remaining_by_currency = {}
            for currency, commitment_total in commitments_by_currency.items():
                salary_in_currency = salary_by_currency.get(currency, Decimal("0"))
                remaining_by_currency[currency] = salary_in_currency - commitment_total

            # Determine coverage analysis
            primary_remaining = remaining_by_currency.get(
                primary_currency, Decimal("0")
            )
            if primary_remaining > 0:
                coverage_analysis = "sufficient"
            elif primary_remaining > -salary_amount * Decimal("0.1"):  # Within 10%
                coverage_analysis = "tight"
            else:
                coverage_analysis = "insufficient"

            # Generate recommendations
            recommendations = self._generate_salary_recommendations(
                coverage_analysis, ending_soon_commitments, finite_commitments
            )

            # Create commitment end analysis
            commitment_end_analysis = self._analyze_commitment_endings(
                finite_commitments + ending_soon_commitments
            )

            return {
                "salary_amount": CurrencyAmounts(salary_by_currency),
                "period_start": next_salary_date.isoformat(),
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
                "currencies_found": list(commitments_by_currency.keys()),
                "primary_currency": primary_currency,
            }

        except Exception as e:
            logger.error(f"❌ Failed to calculate salary breakdown: {e}")
            raise

    async def _estimate_salary_amount(self) -> Decimal:
        """Estimate salary amount based on historical income data."""
        # This would analyze historical income transactions
        # For now, return a placeholder
        return Decimal("5000.00")

    def _generate_salary_recommendations(
        self,
        coverage_analysis: str,
        ending_soon: list[CommitmentBreakdown],
        finite: list[CommitmentBreakdown],
    ) -> list[str]:
        """Generate personalized salary recommendations."""
        recommendations = []

        if coverage_analysis == "insufficient":
            recommendations.append(
                "⚠️ Your commitments exceed your salary. Consider reducing expenses or increasing income."
            )

        if coverage_analysis == "tight":
            recommendations.append(
                "💡 Your budget is tight. Monitor expenses carefully this period."
            )

        if ending_soon:
            total_relief = sum(c.amount for c in ending_soon)
            recommendations.append(
                f"🎉 {len(ending_soon)} commitments ending soon will free up ${total_relief}/month."
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
