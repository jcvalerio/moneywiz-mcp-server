"""Transaction-related MCP tools for MoneyWiz server."""

import logging
from typing import Any

from mcp.types import Tool

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.services.transaction_service import TransactionService
from moneywiz_mcp_server.utils.date_utils import (
    format_date_range_for_display,
    parse_natural_language_date,
)
from moneywiz_mcp_server.utils.formatters import format_currency

logger = logging.getLogger(__name__)


def search_transactions_tool(db_manager: DatabaseManager) -> Tool:
    """
    Create the search_transactions MCP tool.

    Args:
        db_manager: Database manager instance

    Returns:
        Configured MCP Tool for searching transactions
    """

    async def handler(
        time_period: str = "last 3 months",
        account_ids: list[str] | None = None,
        categories: list[str] | None = None,
        transaction_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search and filter transactions based on criteria.

        Args:
            time_period: Natural language time period (e.g., "last 3 months")
            account_ids: Optional list of account IDs to filter
            categories: Optional list of category names to filter
            transaction_type: Optional transaction type filter
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dictionaries
        """
        logger.info(f"Searching transactions for period: {time_period}")

        try:
            # Parse time period
            date_range = parse_natural_language_date(time_period)

            # Convert account IDs to integers if provided
            account_id_ints = None
            if account_ids:
                try:
                    account_id_ints = [int(aid) for aid in account_ids if aid.isdigit()]
                except ValueError as e:
                    logger.warning(f"Invalid account ID format: {e}")

            # Initialize service
            service = TransactionService(db_manager)

            # Get transactions
            transactions = await service.get_transactions(
                start_date=date_range.start_date,
                end_date=date_range.end_date,
                account_ids=account_id_ints,
                categories=categories,
                limit=limit,
            )

            # Format results
            result = []
            for transaction in transactions:
                formatted_transaction = {
                    "id": transaction.id,
                    "date": transaction.date.isoformat(),
                    "description": transaction.description,
                    "amount": format_currency(
                        float(transaction.amount), transaction.currency
                    ),
                    "category": transaction.category or "Uncategorized",
                    "payee": transaction.payee or "Unknown",
                    "account_id": transaction.account_id,
                    "transaction_type": transaction.transaction_type.value,
                    "currency": transaction.currency,
                    "reconciled": transaction.reconciled,
                }

                # Add notes if present
                if transaction.notes:
                    formatted_transaction["notes"] = transaction.notes

                # Add original currency info if different
                if (
                    transaction.original_currency
                    and transaction.original_currency != transaction.currency
                ):
                    formatted_transaction["original_amount"] = format_currency(
                        float(transaction.original_amount or 0),
                        transaction.original_currency,
                    )
                    formatted_transaction["original_currency"] = (
                        transaction.original_currency
                    )

                result.append(formatted_transaction)

            logger.info(
                f"Found {len(result)} transactions for {format_date_range_for_display(date_range)}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to search transactions: {e}")
            raise RuntimeError(f"Failed to search transactions: {e!s}") from e

    return Tool(
        name="search_transactions",
        description="Search and filter transactions with natural language time periods and criteria",
        inputSchema={
            "type": "object",
            "properties": {
                "time_period": {
                    "type": "string",
                    "description": "Time period in natural language (e.g., 'last 3 months', 'this year')",
                    "default": "last 3 months",
                },
                "account_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of account IDs to filter by",
                },
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of category names to filter by",
                },
                "transaction_type": {
                    "type": "string",
                    "description": "Optional transaction type filter",
                    "enum": [
                        "deposit",
                        "withdraw",
                        "transfer_in",
                        "transfer_out",
                        "investment_buy",
                        "investment_sell",
                        "refund",
                    ],
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of transactions to return",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
        },
        handler=handler,
    )


def analyze_expenses_by_category_tool(db_manager: DatabaseManager) -> Tool:
    """
    Create the analyze_expenses_by_category MCP tool.

    Args:
        db_manager: Database manager instance

    Returns:
        Configured MCP Tool for expense analysis by category
    """

    async def handler(
        time_period: str = "last 3 months", top_categories: int = 10
    ) -> dict[str, Any]:
        """
        Analyze expenses by category for the specified time period.

        Args:
            time_period: Natural language time period
            top_categories: Number of top categories to show

        Returns:
            Dictionary with expense analysis by category
        """
        logger.info(f"Analyzing expenses by category for: {time_period}")

        try:
            # Parse time period
            date_range = parse_natural_language_date(time_period)

            # Initialize service
            service = TransactionService(db_manager)

            # Get expense summary
            expense_summary = await service.get_expense_summary(
                start_date=date_range.start_date,
                end_date=date_range.end_date,
                group_by="category",
            )

            # Format results
            total_expenses = expense_summary["total_expenses"]
            categories = expense_summary["category_breakdown"][:top_categories]

            # Build response
            top_categories_list: list[dict[str, Any]] = []
            result = {
                "analysis_period": format_date_range_for_display(date_range),
                "total_expenses": format_currency(float(total_expenses), "USD"),
                "currency": "USD",
                "top_categories": top_categories_list,
                "summary": {
                    "total_categories": len(expense_summary["category_breakdown"]),
                    "total_transactions": sum(
                        cat.transaction_count for cat in categories
                    ),
                    "average_per_category": format_currency(
                        float(total_expenses / len(categories)) if categories else 0,
                        "USD",
                    ),
                },
            }

            # Add top categories
            for i, category in enumerate(categories, 1):
                category_data = {
                    "rank": i,
                    "category": category.category_name,
                    "total_amount": format_currency(
                        float(category.total_amount), "USD"
                    ),
                    "transaction_count": category.transaction_count,
                    "average_amount": format_currency(
                        float(category.average_amount), "USD"
                    ),
                    "percentage_of_total": round(category.percentage_of_total, 1),
                    "impact_level": (
                        "high"
                        if category.percentage_of_total > 20
                        else "medium"
                        if category.percentage_of_total > 10
                        else "low"
                    ),
                }
                result["top_categories"].append(category_data)

            # Add insights
            if categories:
                top_category = categories[0]
                result["insights"] = {
                    "highest_impact_category": top_category.category_name,
                    "highest_impact_amount": format_currency(
                        float(top_category.total_amount), "USD"
                    ),
                    "highest_impact_percentage": round(
                        top_category.percentage_of_total, 1
                    ),
                    "recommendation": f"Consider reviewing spending in {top_category.category_name} "
                    f"as it represents {round(top_category.percentage_of_total, 1)}% of your expenses",
                }

            logger.info(f"Generated expense analysis with {len(categories)} categories")
            return result

        except Exception as e:
            logger.error(f"Failed to analyze expenses by category: {e}")
            raise RuntimeError(f"Failed to analyze expenses by category: {e!s}") from e

    return Tool(
        name="analyze_expenses_by_category",
        description="Analyze expenses by category to identify spending patterns and high-impact categories",
        inputSchema={
            "type": "object",
            "properties": {
                "time_period": {
                    "type": "string",
                    "description": "Time period in natural language (e.g., 'last 3 months', 'this year')",
                    "default": "last 3 months",
                },
                "top_categories": {
                    "type": "integer",
                    "description": "Number of top categories to analyze",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
        },
        handler=handler,
    )


def analyze_income_vs_expenses_tool(db_manager: DatabaseManager) -> Tool:
    """
    Create the analyze_income_vs_expenses MCP tool.

    Args:
        db_manager: Database manager instance

    Returns:
        Configured MCP Tool for income vs expense analysis
    """

    async def handler(time_period: str = "last 3 months") -> dict[str, Any]:
        """
        Analyze income vs expenses and savings potential.

        Args:
            time_period: Natural language time period

        Returns:
            Dictionary with income vs expense analysis
        """
        logger.info(f"Analyzing income vs expenses for: {time_period}")

        try:
            # Parse time period
            date_range = parse_natural_language_date(time_period)

            # Initialize service
            service = TransactionService(db_manager)

            # Get income vs expense analysis
            analysis = await service.get_income_vs_expense(
                start_date=date_range.start_date, end_date=date_range.end_date
            )

            # Format results
            result = {
                "analysis_period": format_date_range_for_display(date_range),
                "financial_overview": {
                    "total_income": format_currency(
                        float(analysis.total_income), analysis.currency
                    ),
                    "total_expenses": format_currency(
                        float(analysis.total_expenses), analysis.currency
                    ),
                    "net_savings": format_currency(
                        float(analysis.net_savings), analysis.currency
                    ),
                    "savings_rate": f"{analysis.savings_rate:.1f}%",
                    "currency": analysis.currency,
                },
                "expense_breakdown": [],
                "savings_analysis": {
                    "status": "positive" if analysis.net_savings > 0 else "negative",
                    "monthly_savings": format_currency(
                        float(analysis.net_savings / 3), analysis.currency
                    ),  # Assuming 3 months
                    "recommendations": [],
                },
            }

            # Add expense breakdown
            for category in analysis.expense_breakdown[:10]:  # Top 10
                result["expense_breakdown"].append(
                    {
                        "category": category.category_name,
                        "amount": format_currency(
                            float(category.total_amount), analysis.currency
                        ),
                        "percentage": round(category.percentage_of_total, 1),
                    }
                )

            # Generate savings recommendations
            if analysis.savings_rate < 10:
                result["savings_analysis"]["recommendations"].append(
                    "Your savings rate is below 10%. Consider reviewing your expenses to identify areas for reduction."
                )
            elif analysis.savings_rate < 20:
                result["savings_analysis"]["recommendations"].append(
                    "Good savings rate! Consider increasing it to 20% for better financial security."
                )
            else:
                result["savings_analysis"]["recommendations"].append(
                    "Excellent savings rate! You're on track for strong financial health."
                )

            # Add expense-specific recommendations
            if analysis.expense_breakdown:
                top_expense = analysis.expense_breakdown[0]
                if top_expense.percentage_of_total > 30:
                    result["savings_analysis"]["recommendations"].append(
                        f"Consider reviewing {top_expense.category_name} expenses, "
                        f"which represent {top_expense.percentage_of_total:.1f}% of your spending."
                    )

            logger.info(
                f"Generated income vs expense analysis with {analysis.savings_rate:.1f}% savings rate"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to analyze income vs expenses: {e}")
            raise RuntimeError(f"Failed to analyze income vs expenses: {e!s}") from e

    return Tool(
        name="analyze_income_vs_expenses",
        description="Analyze income vs expenses to understand savings rate and financial health",
        inputSchema={
            "type": "object",
            "properties": {
                "time_period": {
                    "type": "string",
                    "description": "Time period in natural language (e.g., 'last 3 months', 'this year')",
                    "default": "last 3 months",
                }
            },
        },
        handler=handler,
    )
