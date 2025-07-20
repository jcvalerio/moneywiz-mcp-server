"""Trend analysis service for financial patterns over time."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from ..database.connection import DatabaseManager
from ..models.transaction import TransactionModel

logger = logging.getLogger(__name__)


class TrendService:
    """Service for analyzing financial trends and patterns."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def analyze_spending_trends(
        self,
        months: int = 6,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze spending trends over time.
        
        Args:
            months: Number of months to analyze
            category: Optional specific category to analyze
            
        Returns:
            Dictionary with trend analysis including monthly data and insights
        """
        logger.info(f"Analyzing spending trends for {months} months")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        # Get transaction service
        from .transaction_service import TransactionService
        transaction_service = TransactionService(self.db_manager)
        
        # Get transactions for the period
        transactions = await transaction_service.get_transactions(
            start_date=start_date,
            end_date=end_date
        )
        
        # Group by month
        monthly_data = self._group_transactions_by_month(transactions)
        
        # Calculate trends
        if category:
            trend_data = self._calculate_category_trend(monthly_data, category)
        else:
            trend_data = self._calculate_overall_trend(monthly_data)
        
        # Generate insights
        insights = self._generate_trend_insights(trend_data)
        
        # Calculate projections
        projections = self._calculate_projections(trend_data)
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "months_analyzed": months
            },
            "monthly_data": trend_data["monthly_data"],
            "statistics": {
                "average_monthly": trend_data["average"],
                "median_monthly": trend_data["median"],
                "std_deviation": trend_data["std_dev"],
                "trend_direction": trend_data["direction"],
                "trend_strength": trend_data["strength"],
                "growth_rate": trend_data["growth_rate"]
            },
            "insights": insights,
            "projections": projections,
            "visualizations": self._prepare_visualization_data(trend_data)
        }
    
    async def analyze_category_trends(
        self,
        months: int = 6,
        top_n: int = 5
    ) -> Dict[str, Any]:
        """Analyze trends for top spending categories."""
        logger.info(f"Analyzing category trends for top {top_n} categories")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        # Get expense summary to identify top categories
        from .transaction_service import TransactionService
        transaction_service = TransactionService(self.db_manager)
        
        expense_summary = await transaction_service.get_expense_summary(
            start_date=start_date,
            end_date=end_date,
            group_by="category"
        )
        
        # Analyze each top category
        category_trends = []
        for category_expense in expense_summary["category_breakdown"][:top_n]:
            category_name = category_expense.category_name
            trend = await self.analyze_spending_trends(months, category_name)
            
            category_trends.append({
                "category": category_name,
                "total_spent": float(category_expense.total_amount),
                "percentage_of_total": category_expense.percentage_of_total,
                "trend": trend["statistics"]["trend_direction"],
                "growth_rate": trend["statistics"]["growth_rate"],
                "monthly_average": trend["statistics"]["average_monthly"],
                "insights": trend["insights"][:2]  # Top 2 insights per category
            })
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "months_analyzed": months
            },
            "category_trends": category_trends,
            "overall_insights": self._generate_category_comparison_insights(category_trends)
        }
    
    async def analyze_income_vs_expense_trends(
        self,
        months: int = 12
    ) -> Dict[str, Any]:
        """Analyze income vs expense trends over time."""
        logger.info(f"Analyzing income vs expense trends for {months} months")
        
        end_date = datetime.now()
        monthly_data = []
        
        # Get month-by-month data
        for i in range(months):
            month_end = end_date - timedelta(days=i * 30)
            month_start = month_end - timedelta(days=30)
            
            from .transaction_service import TransactionService
            transaction_service = TransactionService(self.db_manager)
            
            income_expense = await transaction_service.get_income_vs_expense(
                start_date=month_start,
                end_date=month_end
            )
            
            monthly_data.append({
                "month": month_end.strftime("%Y-%m"),
                "income": float(income_expense.total_income),
                "expenses": float(income_expense.total_expenses),
                "net_savings": float(income_expense.net_savings),
                "savings_rate": float(income_expense.savings_rate)
            })
        
        # Reverse to get chronological order
        monthly_data.reverse()
        
        # Calculate trends
        income_trend = self._calculate_trend_metrics([m["income"] for m in monthly_data])
        expense_trend = self._calculate_trend_metrics([m["expenses"] for m in monthly_data])
        savings_trend = self._calculate_trend_metrics([m["savings_rate"] for m in monthly_data])
        
        return {
            "period": {
                "months_analyzed": months
            },
            "monthly_data": monthly_data,
            "trends": {
                "income": {
                    "direction": income_trend["direction"],
                    "growth_rate": income_trend["growth_rate"],
                    "stability": income_trend["stability"]
                },
                "expenses": {
                    "direction": expense_trend["direction"],
                    "growth_rate": expense_trend["growth_rate"],
                    "stability": expense_trend["stability"]
                },
                "savings_rate": {
                    "direction": savings_trend["direction"],
                    "average": savings_trend["average"],
                    "improving": savings_trend["direction"] == "increasing"
                }
            },
            "insights": self._generate_income_expense_insights(
                monthly_data, income_trend, expense_trend, savings_trend
            )
        }
    
    def _group_transactions_by_month(
        self,
        transactions: List[TransactionModel]
    ) -> Dict[str, List[TransactionModel]]:
        """Group transactions by month."""
        monthly_groups = defaultdict(list)
        
        for transaction in transactions:
            if transaction.is_expense():
                month_key = transaction.date.strftime("%Y-%m")
                monthly_groups[month_key].append(transaction)
        
        return dict(monthly_groups)
    
    def _calculate_overall_trend(
        self,
        monthly_data: Dict[str, List[TransactionModel]]
    ) -> Dict[str, Any]:
        """Calculate overall spending trend."""
        monthly_totals = []
        monthly_details = []
        
        # Sort months chronologically
        sorted_months = sorted(monthly_data.keys())
        
        for month in sorted_months:
            transactions = monthly_data[month]
            total = sum(abs(float(t.amount)) for t in transactions)
            monthly_totals.append(total)
            
            monthly_details.append({
                "month": month,
                "total_expenses": total,
                "transaction_count": len(transactions),
                "average_transaction": total / len(transactions) if transactions else 0
            })
        
        trend_metrics = self._calculate_trend_metrics(monthly_totals)
        
        return {
            "monthly_data": monthly_details,
            "average": trend_metrics["average"],
            "median": trend_metrics["median"],
            "std_dev": trend_metrics["std_dev"],
            "direction": trend_metrics["direction"],
            "strength": trend_metrics["strength"],
            "growth_rate": trend_metrics["growth_rate"]
        }
    
    def _calculate_category_trend(
        self,
        monthly_data: Dict[str, List[TransactionModel]],
        category: str
    ) -> Dict[str, Any]:
        """Calculate trend for a specific category."""
        monthly_totals = []
        monthly_details = []
        
        sorted_months = sorted(monthly_data.keys())
        
        for month in sorted_months:
            transactions = monthly_data[month]
            category_transactions = [
                t for t in transactions 
                if t.category and category.lower() in t.category.lower()
            ]
            
            total = sum(abs(float(t.amount)) for t in category_transactions)
            monthly_totals.append(total)
            
            monthly_details.append({
                "month": month,
                "total_expenses": total,
                "transaction_count": len(category_transactions),
                "average_transaction": total / len(category_transactions) 
                                     if category_transactions else 0
            })
        
        trend_metrics = self._calculate_trend_metrics(monthly_totals)
        
        return {
            "monthly_data": monthly_details,
            "category": category,
            "average": trend_metrics["average"],
            "median": trend_metrics["median"],
            "std_dev": trend_metrics["std_dev"],
            "direction": trend_metrics["direction"],
            "strength": trend_metrics["strength"],
            "growth_rate": trend_metrics["growth_rate"]
        }
    
    def _calculate_trend_metrics(self, values: List[float]) -> Dict[str, Any]:
        """Calculate trend metrics from a series of values."""
        if not values:
            return {
                "average": 0,
                "median": 0,
                "std_dev": 0,
                "direction": "stable",
                "strength": "none",
                "growth_rate": 0,
                "stability": "stable"
            }
        
        import statistics
        
        average = statistics.mean(values)
        median = statistics.median(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0
        
        # Calculate trend direction using linear regression
        if len(values) >= 3:
            # Simple linear regression
            n = len(values)
            x = list(range(n))
            xy = sum(i * v for i, v in enumerate(values))
            xx = sum(i * i for i in x)
            x_mean = sum(x) / n
            y_mean = average
            
            if xx - n * x_mean * x_mean != 0:
                slope = (xy - n * x_mean * y_mean) / (xx - n * x_mean * x_mean)
                
                # Determine direction and strength
                growth_rate = (slope / average * 100) if average > 0 else 0
                
                if abs(growth_rate) < 2:
                    direction = "stable"
                    strength = "weak"
                elif growth_rate > 0:
                    direction = "increasing"
                    strength = "strong" if growth_rate > 10 else "moderate"
                else:
                    direction = "decreasing"
                    strength = "strong" if growth_rate < -10 else "moderate"
            else:
                direction = "stable"
                strength = "none"
                growth_rate = 0
        else:
            direction = "insufficient_data"
            strength = "none"
            growth_rate = 0
        
        # Calculate stability
        cv = (std_dev / average * 100) if average > 0 else 0
        stability = "stable" if cv < 20 else "volatile" if cv > 50 else "moderate"
        
        return {
            "average": average,
            "median": median,
            "std_dev": std_dev,
            "direction": direction,
            "strength": strength,
            "growth_rate": growth_rate,
            "stability": stability
        }
    
    def _generate_trend_insights(self, trend_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate insights from trend data."""
        insights = []
        
        # Trend direction insight
        direction = trend_data["direction"]
        strength = trend_data["strength"]
        growth_rate = trend_data["growth_rate"]
        
        if direction == "increasing" and strength == "strong":
            insights.append({
                "type": "warning",
                "title": "Rapidly Increasing Expenses",
                "description": f"Your spending is increasing at {abs(growth_rate):.1f}% per month. "
                              f"Consider reviewing your budget to control expenses.",
                "priority": "high"
            })
        elif direction == "decreasing" and strength == "strong":
            insights.append({
                "type": "positive",
                "title": "Great Progress on Expense Reduction",
                "description": f"Your spending is decreasing at {abs(growth_rate):.1f}% per month. "
                              f"Keep up the good work!",
                "priority": "low"
            })
        
        # Volatility insight
        std_dev = trend_data["std_dev"]
        average = trend_data["average"]
        if average > 0:
            cv = (std_dev / average) * 100
            if cv > 30:
                insights.append({
                    "type": "info",
                    "title": "High Spending Variability",
                    "description": "Your monthly spending varies significantly. "
                                  "Consider creating a more consistent budget.",
                    "priority": "medium"
                })
        
        return insights
    
    def _calculate_projections(
        self,
        trend_data: Dict[str, Any],
        months_ahead: int = 3
    ) -> List[Dict[str, Any]]:
        """Calculate spending projections based on trends."""
        projections = []
        
        if trend_data["direction"] == "insufficient_data":
            return projections
        
        current_average = trend_data["average"]
        growth_rate = trend_data["growth_rate"] / 100  # Convert to decimal
        
        for i in range(1, months_ahead + 1):
            projected_amount = current_average * (1 + growth_rate) ** i
            
            future_date = datetime.now() + timedelta(days=i * 30)
            projections.append({
                "month": future_date.strftime("%Y-%m"),
                "projected_amount": projected_amount,
                "confidence": "high" if trend_data["strength"] == "strong" else "medium"
            })
        
        return projections
    
    def _prepare_visualization_data(self, trend_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for visualization."""
        monthly_data = trend_data["monthly_data"]
        
        return {
            "line_chart": {
                "labels": [d["month"] for d in monthly_data],
                "datasets": [{
                    "label": "Monthly Expenses",
                    "data": [d["total_expenses"] for d in monthly_data]
                }]
            },
            "bar_chart": {
                "labels": [d["month"] for d in monthly_data],
                "datasets": [{
                    "label": "Transaction Count",
                    "data": [d["transaction_count"] for d in monthly_data]
                }]
            }
        }
    
    def _generate_category_comparison_insights(
        self,
        category_trends: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate insights from category trend comparison."""
        insights = []
        
        # Find fastest growing category
        fastest_growing = max(category_trends, key=lambda x: x["growth_rate"])
        if fastest_growing["growth_rate"] > 5:
            insights.append({
                "type": "warning",
                "title": f"Fastest Growing Category: {fastest_growing['category']}",
                "description": f"Spending on {fastest_growing['category']} is growing at "
                              f"{fastest_growing['growth_rate']:.1f}% per month.",
                "priority": "high"
            })
        
        # Find most stable category
        stable_categories = [c for c in category_trends if c["trend"] == "stable"]
        if stable_categories:
            insights.append({
                "type": "info",
                "title": "Stable Spending Categories",
                "description": f"{len(stable_categories)} categories show stable spending patterns, "
                              f"indicating good budget control.",
                "priority": "low"
            })
        
        return insights
    
    def _generate_income_expense_insights(
        self,
        monthly_data: List[Dict[str, Any]],
        income_trend: Dict[str, Any],
        expense_trend: Dict[str, Any],
        savings_trend: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate insights from income vs expense trends."""
        insights = []
        
        # Income vs expense growth comparison
        if expense_trend["growth_rate"] > income_trend["growth_rate"]:
            insights.append({
                "type": "warning",
                "title": "Expenses Growing Faster Than Income",
                "description": f"Your expenses are growing {expense_trend['growth_rate']:.1f}% "
                              f"while income is growing {income_trend['growth_rate']:.1f}%. "
                              f"This trend is unsustainable.",
                "priority": "high"
            })
        
        # Savings rate trend
        if savings_trend["direction"] == "decreasing":
            insights.append({
                "type": "warning",
                "title": "Declining Savings Rate",
                "description": "Your savings rate has been declining. "
                              "Review your budget to reverse this trend.",
                "priority": "high"
            })
        elif savings_trend["direction"] == "increasing":
            insights.append({
                "type": "positive",
                "title": "Improving Savings Rate",
                "description": f"Great job! Your average savings rate is {savings_trend['average']:.1f}% "
                              f"and improving.",
                "priority": "low"
            })
        
        return insights