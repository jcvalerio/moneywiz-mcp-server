"""Service for budget operations and spending analysis."""

from datetime import datetime, timedelta
from decimal import Decimal
import logging
from typing import Any, ClassVar

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.budget import (
    BudgetAnalysisResponse,
    BudgetCategoryBreakdown,
    BudgetModel,
    BudgetPeriod,
    BudgetStatus,
    BudgetVsActualItem,
    BudgetVsActualResponse,
)
from moneywiz_mcp_server.models.currency_types import CurrencyAmounts

logger = logging.getLogger(__name__)


class BudgetService:
    """Service for budget operations and spending analysis."""

    # Duration units mapping (same as scheduled transactions)
    DURATION_UNITS: ClassVar[dict[int, BudgetPeriod]] = {
        1: BudgetPeriod.DAILY,
        2: BudgetPeriod.WEEKLY,
        4: BudgetPeriod.YEARLY,
        8: BudgetPeriod.MONTHLY,
    }

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._category_cache: dict[int, str] = {}
        self._account_cache: dict[int, str] = {}

    async def get_budgets(
        self,
        categories: list[str] | None = None,
        period: str | None = None,
        include_inactive: bool = False,
        limit: int | None = None,
    ) -> list[BudgetModel]:
        """
        Get budgets with spending status.

        Args:
            categories: Optional list of category names to filter by
            period: Optional period filter (daily, weekly, monthly, yearly)
            include_inactive: Include inactive budgets
            limit: Maximum number of results

        Returns:
            List of BudgetModel objects with spending data
        """
        try:
            logger.info("📊 Fetching budgets...")

            budgets = []

            # Query Entity 18 for budget definitions
            query = """
                SELECT * FROM ZSYNCOBJECT
                WHERE Z_ENT = 18
            """

            records = await self.db_manager.execute_query(query)

            if not records:
                logger.info("No budget records found")
                return []

            logger.info(f"Found {len(records)} budget definition records")

            for record in records:
                budget = await self._convert_record_to_model(record)
                if budget and await self._matches_filters(budget, categories, period):
                    budgets.append(budget)

            # Apply limit
            if limit:
                budgets = budgets[:limit]

            logger.info(f"Returning {len(budgets)} budgets after filtering")
            return budgets

        except Exception as e:
            logger.error(f"Failed to get budgets: {e}")
            raise

    async def _convert_record_to_model(
        self, record: dict[str, Any]
    ) -> BudgetModel | None:
        """Convert database record to BudgetModel."""
        try:
            budget_pk = record.get("Z_PK")
            if not budget_pk:
                return None

            # Get budget amount from ZOPENINGBALANCE1
            budget_amount = Decimal(str(record.get("ZOPENINGBALANCE1") or 0))
            if budget_amount <= 0:
                return None  # Skip zero or negative budgets

            # Determine period from ZDURATIONUNITS
            duration_units = record.get("ZDURATIONUNITS", 8)
            period = self.DURATION_UNITS.get(duration_units, BudgetPeriod.MONTHLY)

            # Get categories linked to this budget
            categories = await self._get_budget_categories(budget_pk)

            # Get linked accounts
            linked_accounts = await self._get_linked_accounts(budget_pk)

            # Calculate spent amount from linked transactions
            spent_data = await self._calculate_spent_amount(budget_pk)
            spent_amount = spent_data.get("spent", Decimal("0"))
            transaction_count = spent_data.get("count", 0)

            # Calculate remaining and percentage
            remaining_amount = budget_amount - spent_amount
            percentage_used = (
                float(spent_amount / budget_amount * 100) if budget_amount > 0 else 0.0
            )

            # Determine status
            if percentage_used >= 100:
                status = BudgetStatus.OVER_BUDGET
            elif percentage_used >= 80:
                status = BudgetStatus.AT_RISK
            else:
                status = BudgetStatus.ON_TRACK

            # Get creation date
            created_date = None
            creation_ts = record.get("ZOBJECTCREATIONDATE")
            if creation_ts:
                created_date = self._core_data_timestamp_to_datetime(creation_ts)

            # Build category name for display
            name = None
            if categories:
                if len(categories) == 1:
                    name = categories[0]
                else:
                    name = f"{categories[0]} (+{len(categories) - 1} more)"

            return BudgetModel(
                id=str(budget_pk),
                name=name,
                categories=categories,
                budget_amount=budget_amount,
                currency="CRC",  # Default, could be enhanced
                period=period,
                spent_amount=spent_amount,
                remaining_amount=remaining_amount,
                percentage_used=percentage_used,
                status=status,
                is_repeatable=bool(record.get("ZISREPEATABLE", 1)),
                is_active=True,
                linked_accounts=linked_accounts,
                transaction_count=transaction_count,
                created_date=created_date,
                database_id=budget_pk,
                entity_type=18,
            )

        except Exception as e:
            logger.warning(f"Failed to convert record to budget model: {e}")
            return None

    async def _get_budget_categories(self, budget_pk: int) -> list[str]:
        """Get category names linked to a budget."""
        try:
            query = """
                SELECT DISTINCT so.ZNAME2 as category_name
                FROM ZCATEGORYASSIGMENT ca
                JOIN ZSYNCOBJECT so ON ca.ZCATEGORY = so.Z_PK
                WHERE ca.ZBUDGET = ? AND so.ZNAME2 IS NOT NULL
            """
            results = await self.db_manager.execute_query(query, (budget_pk,))
            return [r["category_name"] for r in results if r.get("category_name")]
        except Exception as e:
            logger.warning(f"Failed to get budget categories: {e}")
            return []

    async def _get_linked_accounts(self, budget_pk: int) -> list[str]:
        """Get account names linked to a budget."""
        try:
            query = """
                SELECT DISTINCT so.ZNAME as account_name
                FROM ZACCOUNTBUDGETLINK abl
                JOIN ZSYNCOBJECT so ON abl.ZACCOUNT = so.Z_PK
                WHERE abl.ZBUDGET = ? AND so.ZNAME IS NOT NULL
            """
            results = await self.db_manager.execute_query(query, (budget_pk,))
            return [r["account_name"] for r in results if r.get("account_name")]
        except Exception as e:
            logger.warning(f"Failed to get linked accounts: {e}")
            return []

    async def _calculate_spent_amount(self, budget_pk: int) -> dict[str, Any]:
        """Calculate total spent amount for a budget from linked transactions."""
        try:
            # Get current month date range for filtering
            now = datetime.now()
            start_of_month = datetime(now.year, now.month, 1)
            start_ts = self._datetime_to_core_data_timestamp(start_of_month)

            query = """
                SELECT
                    SUM(ABS(t.ZAMOUNT1)) as spent,
                    COUNT(t.Z_PK) as count
                FROM ZTRANSACTIONBUDGETLINK tbl
                JOIN ZSYNCOBJECT t ON tbl.ZTRANSACTION = t.Z_PK
                WHERE tbl.ZBUDGET = ?
                  AND t.ZAMOUNT1 < 0
                  AND t.ZDATE1 >= ?
            """
            results = await self.db_manager.execute_query(query, (budget_pk, start_ts))

            if results and results[0].get("spent"):
                return {
                    "spent": Decimal(str(results[0]["spent"])),
                    "count": results[0].get("count", 0),
                }

            # Also check ZPASTPERIODSBUDGET linkage
            query2 = """
                SELECT
                    SUM(ABS(t.ZAMOUNT1)) as spent,
                    COUNT(t.Z_PK) as count
                FROM ZTRANSACTIONBUDGETLINK tbl
                JOIN ZSYNCOBJECT t ON tbl.ZTRANSACTION = t.Z_PK
                WHERE tbl.ZPASTPERIODSBUDGET = ?
                  AND t.ZAMOUNT1 < 0
                  AND t.ZDATE1 >= ?
            """
            results2 = await self.db_manager.execute_query(
                query2, (budget_pk, start_ts)
            )

            if results2 and results2[0].get("spent"):
                return {
                    "spent": Decimal(str(results2[0]["spent"])),
                    "count": results2[0].get("count", 0),
                }

            return {"spent": Decimal("0"), "count": 0}

        except Exception as e:
            logger.warning(f"Failed to calculate spent amount: {e}")
            return {"spent": Decimal("0"), "count": 0}

    async def _matches_filters(
        self,
        budget: BudgetModel,
        categories: list[str] | None,
        period: str | None,
    ) -> bool:
        """Check if budget matches the specified filters."""
        # Category filter
        if categories and not any(
            cat.lower() in [c.lower() for c in budget.categories] for cat in categories
        ):
            return False

        # Period filter
        if period and budget.period.value.lower() != period.lower():
            return False

        return True

    async def get_budget_analysis(
        self,
        time_period: str = "current_month",
    ) -> dict[str, Any]:
        """
        Analyze overall budget performance.

        Args:
            time_period: Period to analyze

        Returns:
            Budget analysis data
        """
        try:
            logger.info(f"📊 Analyzing budgets for {time_period}...")

            budgets = await self.get_budgets()

            if not budgets:
                return self._empty_analysis()

            # Aggregate statistics
            total_budgeted = Decimal("0")
            total_spent = Decimal("0")
            on_track = 0
            at_risk = 0
            over_budget = 0
            category_breakdown = []

            for budget in budgets:
                total_budgeted += budget.budget_amount
                total_spent += budget.spent_amount

                if budget.status == BudgetStatus.ON_TRACK:
                    on_track += 1
                elif budget.status == BudgetStatus.AT_RISK:
                    at_risk += 1
                else:
                    over_budget += 1

                # Add to category breakdown if it has categories
                if budget.categories:
                    category_breakdown.append(
                        BudgetCategoryBreakdown(
                            category=budget.categories[0],
                            budget_amount=float(budget.budget_amount),
                            spent_amount=float(budget.spent_amount),
                            remaining_amount=float(budget.remaining_amount),
                            percentage_used=budget.percentage_used,
                            status=budget.status.value,
                            transaction_count=budget.transaction_count,
                        )
                    )

            total_remaining = total_budgeted - total_spent
            overall_percentage = (
                float(total_spent / total_budgeted * 100) if total_budgeted > 0 else 0.0
            )

            # Determine overall status
            if overall_percentage >= 100:
                overall_status = "over_budget"
            elif overall_percentage >= 80:
                overall_status = "at_risk"
            else:
                overall_status = "on_track"

            # Generate recommendations
            recommendations = self._generate_recommendations(
                budgets, overall_percentage, over_budget
            )

            return {
                "analysis_period": time_period,
                "total_budgeted": CurrencyAmounts({"CRC": total_budgeted}),
                "total_spent": CurrencyAmounts({"CRC": total_spent}),
                "total_remaining": CurrencyAmounts({"CRC": total_remaining}),
                "overall_percentage_used": overall_percentage,
                "overall_status": overall_status,
                "budgets_on_track": on_track,
                "budgets_at_risk": at_risk,
                "budgets_over": over_budget,
                "category_breakdown": category_breakdown,
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"Failed to analyze budgets: {e}")
            raise

    async def get_budget_vs_actual(
        self,
        category: str | None = None,
        period: str = "current_month",
    ) -> dict[str, Any]:
        """
        Compare budgeted amounts against actual spending.

        Args:
            category: Optional specific category to analyze
            period: Period to analyze

        Returns:
            Budget vs actual comparison data
        """
        try:
            logger.info(f"📊 Getting budget vs actual for {period}...")

            # Get budgets, optionally filtered by category
            categories = [category] if category else None
            budgets = await self.get_budgets(categories=categories)

            if not budgets:
                return self._empty_comparison(period)

            items = []
            total_budgeted = Decimal("0")
            total_actual = Decimal("0")

            for budget in budgets:
                total_budgeted += budget.budget_amount
                total_actual += budget.spent_amount

                variance = budget.budget_amount - budget.spent_amount
                variance_pct = (
                    float(variance / budget.budget_amount * 100)
                    if budget.budget_amount > 0
                    else 0.0
                )

                primary_category = (
                    budget.categories[0] if budget.categories else "Uncategorized"
                )

                items.append(
                    BudgetVsActualItem(
                        category=primary_category,
                        budgeted=float(budget.budget_amount),
                        actual=float(budget.spent_amount),
                        variance=float(variance),
                        variance_percentage=variance_pct,
                        status=budget.status.value,
                    )
                )

            total_variance = total_budgeted - total_actual

            # Summary statistics
            under_budget_count = sum(
                1 for b in budgets if b.status == BudgetStatus.ON_TRACK
            )
            over_budget_count = sum(
                1 for b in budgets if b.status == BudgetStatus.OVER_BUDGET
            )

            return {
                "period": period,
                "total_budgeted": CurrencyAmounts({"CRC": total_budgeted}),
                "total_actual": CurrencyAmounts({"CRC": total_actual}),
                "total_variance": CurrencyAmounts({"CRC": total_variance}),
                "items": items,
                "summary": {
                    "total_budgets": len(budgets),
                    "under_budget": under_budget_count,
                    "over_budget": over_budget_count,
                    "overall_variance_percentage": float(
                        total_variance / total_budgeted * 100
                    )
                    if total_budgeted > 0
                    else 0.0,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get budget vs actual: {e}")
            raise

    def _generate_recommendations(
        self,
        budgets: list[BudgetModel],
        overall_percentage: float,
        over_budget_count: int,
    ) -> list[str]:
        """Generate budget recommendations based on analysis."""
        recommendations = []

        if over_budget_count > 0:
            recommendations.append(
                f"⚠️ {over_budget_count} budget(s) are over limit - review spending in those categories"
            )

        if overall_percentage >= 80:
            recommendations.append(
                "💡 Overall spending is high - consider reducing discretionary expenses"
            )

        at_risk_budgets = [b for b in budgets if b.status == BudgetStatus.AT_RISK]
        if at_risk_budgets:
            categories = [b.categories[0] for b in at_risk_budgets if b.categories][:3]
            if categories:
                recommendations.append(f"👀 Watch spending in: {', '.join(categories)}")

        if overall_percentage < 50:
            recommendations.append("✅ Good job! You're well within budget this period")

        if not recommendations:
            recommendations.append("📊 Budget tracking is on track")

        return recommendations

    def _empty_analysis(self) -> dict[str, Any]:
        """Return empty analysis structure."""
        return {
            "analysis_period": "current_month",
            "total_budgeted": CurrencyAmounts({}),
            "total_spent": CurrencyAmounts({}),
            "total_remaining": CurrencyAmounts({}),
            "overall_percentage_used": 0.0,
            "overall_status": "no_data",
            "budgets_on_track": 0,
            "budgets_at_risk": 0,
            "budgets_over": 0,
            "category_breakdown": [],
            "recommendations": [
                "No budgets found - create budgets in MoneyWiz to track spending"
            ],
        }

    def _empty_comparison(self, period: str) -> dict[str, Any]:
        """Return empty comparison structure."""
        return {
            "period": period,
            "total_budgeted": CurrencyAmounts({}),
            "total_actual": CurrencyAmounts({}),
            "total_variance": CurrencyAmounts({}),
            "items": [],
            "summary": {
                "total_budgets": 0,
                "under_budget": 0,
                "over_budget": 0,
                "overall_variance_percentage": 0.0,
            },
        }

    def _core_data_timestamp_to_datetime(self, timestamp: float) -> datetime:
        """Convert Core Data timestamp to datetime.

        Core Data uses January 1, 2001 as the reference date.
        """
        core_data_epoch = datetime(2001, 1, 1)
        return core_data_epoch + timedelta(seconds=timestamp)

    def _datetime_to_core_data_timestamp(self, dt: datetime) -> float:
        """Convert datetime to Core Data timestamp."""
        core_data_epoch = datetime(2001, 1, 1)
        return (dt - core_data_epoch).total_seconds()
