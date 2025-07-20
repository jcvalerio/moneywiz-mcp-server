"""Savings optimization and recommendation service."""

from datetime import datetime
from decimal import Decimal
import logging
from typing import Any

from ..database.connection import DatabaseManager
from ..models.analytics_result import CategoryExpense

logger = logging.getLogger(__name__)


class SavingsService:
    """Service for savings analysis and optimization recommendations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def get_savings_recommendations(
        self,
        start_date: datetime,
        end_date: datetime,
        target_savings_rate: float = 20.0,
    ) -> dict[str, Any]:
        """
        Generate personalized savings recommendations based on spending patterns.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            target_savings_rate: Target savings rate percentage (default 20%)

        Returns:
            Dictionary with savings recommendations and actionable insights
        """
        logger.info("Generating savings recommendations")

        # Get income vs expense data
        from .transaction_service import TransactionService

        transaction_service = TransactionService(self.db_manager)

        income_expense = await transaction_service.get_income_vs_expense(
            start_date, end_date
        )

        # Get expense breakdown by category
        expense_summary = await transaction_service.get_expense_summary(
            start_date, end_date, group_by="category"
        )

        # Calculate current state
        current_savings_rate = float(income_expense.savings_rate)
        total_income = float(income_expense.total_income)
        total_expenses = float(income_expense.total_expenses)
        net_savings = float(income_expense.net_savings)

        # Generate recommendations
        recommendations = []
        potential_savings = Decimal("0")

        # 1. Category-based recommendations
        category_recommendations = await self._get_category_recommendations(
            expense_summary["category_breakdown"], total_expenses
        )
        recommendations.extend(category_recommendations["recommendations"])
        potential_savings += category_recommendations["potential_savings"]

        # 2. Fixed vs variable expense analysis
        fixed_variable = await self._analyze_fixed_vs_variable_expenses(
            start_date, end_date
        )
        recommendations.extend(fixed_variable["recommendations"])

        # 3. Spending pattern insights
        spending_patterns = await self._analyze_spending_patterns(start_date, end_date)
        recommendations.extend(spending_patterns["recommendations"])

        # 4. Target savings recommendations
        if current_savings_rate < target_savings_rate:
            needed_reduction = self._calculate_needed_expense_reduction(
                total_income, total_expenses, target_savings_rate
            )
            recommendations.append(
                {
                    "type": "target_savings",
                    "priority": "high",
                    "title": "Reach Target Savings Rate",
                    "description": f"To achieve your {target_savings_rate}% savings target, "
                    f"reduce expenses by ${needed_reduction:.2f}/month",
                    "impact": f"${needed_reduction:.2f}",
                    "difficulty": "medium",
                }
            )

        # Calculate projected savings
        projected_savings_rate = (
            (net_savings + float(potential_savings)) / total_income * 100
            if total_income > 0
            else 0
        )

        return {
            "current_state": {
                "savings_rate": current_savings_rate,
                "monthly_savings": net_savings / ((end_date - start_date).days / 30),
                "total_income": total_income,
                "total_expenses": total_expenses,
            },
            "target_state": {
                "target_savings_rate": target_savings_rate,
                "projected_savings_rate": projected_savings_rate,
                "potential_monthly_savings": float(potential_savings),
                "needed_expense_reduction": float(
                    self._calculate_needed_expense_reduction(
                        total_income, total_expenses, target_savings_rate
                    )
                )
                if current_savings_rate < target_savings_rate
                else 0,
            },
            "recommendations": sorted(
                recommendations, key=lambda x: x.get("priority_score", 0), reverse=True
            )[
                :10
            ],  # Top 10 recommendations
            "insights": {
                "fixed_vs_variable": fixed_variable["insights"],
                "spending_patterns": spending_patterns["insights"],
                "category_analysis": category_recommendations["insights"],
            },
        }

    async def _get_category_recommendations(
        self, category_breakdown: list[CategoryExpense], total_expenses: float
    ) -> dict[str, Any]:
        """Generate recommendations based on category spending."""
        recommendations = []
        potential_savings = Decimal("0")
        insights = {}

        # Analyze top spending categories
        for category in category_breakdown[:5]:  # Top 5 categories
            category_name = category.category_name
            category_amount = float(category.total_amount)
            category_percentage = category.percentage_of_total

            # High spending categories (>20% of total)
            if category_percentage > 20:
                reduction_target = category_amount * 0.15  # Suggest 15% reduction
                recommendations.append(
                    {
                        "type": "category_reduction",
                        "priority": "high",
                        "priority_score": category_percentage,
                        "title": f"Reduce {category_name} Spending",
                        "description": f"{category_name} represents {category_percentage:.1f}% "
                        f"of your expenses. Consider reducing by 15%.",
                        "impact": f"${reduction_target:.2f}/month",
                        "difficulty": "medium",
                        "category": category_name,
                        "current_amount": category_amount,
                        "suggested_amount": category_amount * 0.85,
                    }
                )
                potential_savings += Decimal(str(reduction_target))

            # Discretionary spending categories
            if category_name.lower() in [
                "entertainment",
                "dining out",
                "shopping",
                "hobbies",
                "subscriptions",
            ]:
                reduction_target = category_amount * 0.25  # Suggest 25% reduction
                recommendations.append(
                    {
                        "type": "discretionary_reduction",
                        "priority": "medium",
                        "priority_score": category_percentage * 0.8,
                        "title": f"Optimize {category_name} Spending",
                        "description": f"Discretionary spending on {category_name} "
                        f"could be reduced by 25% without major lifestyle impact.",
                        "impact": f"${reduction_target:.2f}/month",
                        "difficulty": "easy",
                        "category": category_name,
                        "tips": self._get_category_saving_tips(category_name),
                    }
                )
                potential_savings += Decimal(str(reduction_target))

        # Category diversity insight
        top_3_percentage = sum(
            cat.percentage_of_total for cat in category_breakdown[:3]
        )
        insights["concentration"] = {
            "top_3_percentage": top_3_percentage,
            "is_concentrated": top_3_percentage > 60,
            "message": "Your spending is highly concentrated"
            if top_3_percentage > 60
            else "Your spending is well diversified",
        }

        return {
            "recommendations": recommendations,
            "potential_savings": potential_savings,
            "insights": insights,
        }

    async def _analyze_fixed_vs_variable_expenses(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Analyze fixed vs variable expenses."""
        recommendations = []
        insights = {}

        # Categories typically considered fixed
        fixed_categories = [
            "rent",
            "mortgage",
            "insurance",
            "loan payments",
            "utilities",
            "phone",
            "internet",
        ]

        # Get all transactions
        from .transaction_service import TransactionService

        transaction_service = TransactionService(self.db_manager)

        # This is simplified - in reality would need more sophisticated analysis
        expense_summary = await transaction_service.get_expense_summary(
            start_date, end_date, group_by="category"
        )

        fixed_total = Decimal("0")
        variable_total = Decimal("0")

        for category in expense_summary["category_breakdown"]:
            if any(
                fixed in category.category_name.lower() for fixed in fixed_categories
            ):
                fixed_total += category.total_amount
            else:
                variable_total += category.total_amount

        total = fixed_total + variable_total
        fixed_percentage = (fixed_total / total * 100) if total > 0 else 0

        insights["fixed_percentage"] = float(fixed_percentage)
        insights["variable_percentage"] = float(100 - fixed_percentage)

        if fixed_percentage > 50:
            recommendations.append(
                {
                    "type": "fixed_expense_warning",
                    "priority": "high",
                    "priority_score": fixed_percentage / 10,
                    "title": "High Fixed Expenses",
                    "description": f"Your fixed expenses are {fixed_percentage:.1f}% of total. "
                    f"Consider negotiating or switching providers.",
                    "impact": "Varies",
                    "difficulty": "medium",
                    "tips": [
                        "Review and negotiate insurance premiums",
                        "Consider refinancing loans for better rates",
                        "Switch to more affordable phone/internet plans",
                        "Review subscription services",
                    ],
                }
            )

        return {"recommendations": recommendations, "insights": insights}

    async def _analyze_spending_patterns(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Analyze spending patterns for insights."""
        recommendations = []
        insights = {}

        # This would analyze:
        # - Weekend vs weekday spending
        # - Beginning vs end of month patterns
        # - Seasonal variations
        # - Impulse purchase patterns

        # Simplified example
        recommendations.append(
            {
                "type": "spending_pattern",
                "priority": "medium",
                "priority_score": 5,
                "title": "Track Weekend Spending",
                "description": "Consider setting weekend spending limits to reduce impulse purchases.",
                "impact": "10-15% reduction",
                "difficulty": "easy",
                "tips": [
                    "Set a weekend budget",
                    "Use cash for discretionary spending",
                    "Plan activities in advance",
                ],
            }
        )

        insights["patterns_detected"] = ["weekend_spike", "end_of_month_reduction"]

        return {"recommendations": recommendations, "insights": insights}

    def _calculate_needed_expense_reduction(
        self, income: float, expenses: float, target_rate: float
    ) -> float:
        """Calculate how much expenses need to be reduced to hit target savings rate."""
        if income <= 0:
            return 0

        target_expenses = income * (1 - target_rate / 100)
        needed_reduction = expenses - target_expenses

        return max(0, needed_reduction)

    def _get_category_saving_tips(self, category: str) -> list[str]:
        """Get specific saving tips for a category."""
        tips_map = {
            "dining out": [
                "Cook more meals at home",
                "Use restaurant deals and happy hours",
                "Limit dining out to special occasions",
            ],
            "entertainment": [
                "Look for free local events",
                "Use streaming services instead of cable",
                "Take advantage of matinee prices",
            ],
            "shopping": [
                "Create a shopping list and stick to it",
                "Wait 24 hours before non-essential purchases",
                "Compare prices online before buying",
            ],
            "groceries": [
                "Meal plan to reduce waste",
                "Buy generic brands",
                "Use coupons and store loyalty programs",
            ],
            "transportation": [
                "Carpool or use public transit",
                "Combine errands to save gas",
                "Consider walking or biking for short trips",
            ],
        }

        category_lower = category.lower()
        for key, tips in tips_map.items():
            if key in category_lower:
                return tips

        return ["Review spending in this category", "Set a monthly budget limit"]
