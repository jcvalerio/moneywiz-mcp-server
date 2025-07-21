#!/usr/bin/env python3
"""MoneyWiz MCP Server - Modern FastMCP implementation."""
# mypy: disable-error-code=misc

import logging
from pathlib import Path
import sys

from mcp.server import FastMCP

from .config import Config
from .database.connection import DatabaseManager
from .models.responses import (
    AccountDetailResponse,
    AccountListResponse,
    AccountResponse,
    ExpenseAnalysisResponse,
    IncomeVsExpensesResponse,
    TransactionListResponse,
)
from .models.savings_responses import (
    CategoryTrendsResponse,
    IncomeVsExpenseTrendsResponse,
    SavingsOptimizationResponse,
    SpendingTrendResponse,
)
from .services.savings_service import SavingsService
from .services.transaction_service import TransactionService
from .services.trend_service import TrendService

# Import tools at top level to avoid PLC0415 errors
# Legacy tool imports removed - using FastMCP decorators instead
# Import additional utilities to avoid inline imports
from .utils.date_utils import format_date_range_for_display, parse_natural_language_date
from .utils.env_loader import load_env_file

# Configure logging to stderr (MCP best practice)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_env_file()


# Server context removed - tools now manage their own database connections


# Lifespan management removed - tools handle their own database connections


# Create FastMCP server instance
mcp = FastMCP("moneywiz-mcp-server")


async def get_db_manager() -> DatabaseManager:
    """Helper function to get database manager for tools."""
    config = mcp._config
    db_manager = DatabaseManager(config.database_path, read_only=config.read_only)
    await db_manager.initialize()
    return db_manager


@mcp.tool()
async def list_accounts(
    include_hidden: bool = False, account_type: str | None = None
) -> AccountListResponse:
    """
    List all MoneyWiz accounts with current balances.

    Args:
        include_hidden: Include hidden/archived accounts in results
        account_type: Filter by account type (checking, savings, credit_card, etc.)

    Returns:
        List of accounts with balances and metadata
    """
    logger.info(f"📋 Listing accounts (hidden={include_hidden}, type={account_type})")

    try:
        # Get database manager
        db_manager = await get_db_manager()

        try:
            # Use account service for clean separation of concerns
            from .services.account_service import AccountService

            account_service = AccountService(db_manager)
            accounts_data = await account_service.list_accounts(
                include_hidden=include_hidden, account_type=account_type
            )

            # Convert to structured response
            accounts = [AccountResponse(**account) for account in accounts_data]

            return AccountListResponse(
                accounts=accounts,
                total_count=len(accounts),
                filters_applied={
                    "include_hidden": include_hidden,
                    "account_type": account_type,
                },
            )
        finally:
            await db_manager.close()

    except Exception as e:
        logger.error(f"❌ Failed to list accounts: {e}")
        raise RuntimeError(f"Failed to retrieve accounts: {e!s}") from e


@mcp.tool()
async def get_account(
    account_id: str, include_transactions: bool = False
) -> AccountDetailResponse:
    """
    Get detailed information about a specific account.

    Args:
        account_id: Unique identifier for the account
        include_transactions: Include recent transactions in response

    Returns:
        Detailed account information with optional transactions
    """
    logger.info(
        f"🔍 Getting account {account_id} (transactions={include_transactions})"
    )

    try:
        # Get database manager
        db_manager = await get_db_manager()

        try:
            # Use account service for clean separation of concerns
            from .services.account_service import AccountService

            account_service = AccountService(db_manager)
            account_data = await account_service.get_account(
                account_id=account_id, include_transactions=include_transactions
            )

            return AccountDetailResponse(**account_data)
        finally:
            await db_manager.close()

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get account {account_id}: {e}")
        raise RuntimeError(f"Failed to retrieve account details: {e!s}") from e


@mcp.tool()
async def search_transactions(
    time_period: str = "last 3 months",
    account_ids: list[str] | None = None,
    categories: list[str] | None = None,
    transaction_type: str | None = None,
    limit: int = 100,
) -> TransactionListResponse:
    """
    Search and filter transactions with natural language time periods.

    Args:
        time_period: Natural language time period (e.g., 'last 3 months', 'this year')
        account_ids: Optional list of account IDs to filter by
        categories: Optional list of category names to filter by
        transaction_type: Optional transaction type filter
        limit: Maximum number of transactions to return (1-1000)

    Returns:
        List of matching transactions with metadata
    """
    logger.info(f"🔍 Searching transactions for '{time_period}'")

    try:
        # Get database manager
        db_manager = await get_db_manager()

        try:
            from .utils.date_utils import (
                format_date_range_for_display,
                parse_natural_language_date,
            )

            # Parse the time period for metadata
            date_range = parse_natural_language_date(time_period)

            # Use transaction service directly
            transaction_service = TransactionService(db_manager)
            date_range = parse_natural_language_date(time_period)
            transactions = await transaction_service.get_transactions(
                start_date=date_range.start_date,
                end_date=date_range.end_date,
                account_ids=[int(aid) for aid in account_ids] if account_ids else None,
                categories=categories,
                limit=limit,
            )

            # Format transactions data
            from .models.responses import TransactionResponse

            transactions_data = [
                TransactionResponse(
                    id=str(transaction.id),
                    date=transaction.date.isoformat(),
                    description=transaction.description,
                    amount=f"{float(transaction.amount):.2f} {transaction.currency}",
                    category=transaction.category or "Uncategorized",
                    payee=transaction.payee or "Unknown",
                    account_id=str(transaction.account_id),
                    transaction_type=transaction.transaction_type.value,
                    currency=transaction.currency,
                    reconciled=False,
                    notes=None,
                )
                for transaction in transactions
            ]

            return TransactionListResponse(
                transactions=transactions_data,
                total_count=len(transactions_data),
                date_range=format_date_range_for_display(date_range),
                filters_applied={
                    "time_period": time_period,
                    "account_ids": account_ids,
                    "categories": categories,
                    "transaction_type": transaction_type,
                    "limit": limit,
                },
            )
        finally:
            await db_manager.close()

    except Exception as e:
        logger.error(f"❌ Failed to search transactions: {e}")
        raise RuntimeError(f"Failed to search transactions: {e!s}") from e


@mcp.tool()
async def analyze_expenses_by_category(
    time_period: str = "last 3 months", top_categories: int = 10
) -> ExpenseAnalysisResponse:
    """
    Analyze expenses by category to identify spending patterns.

    Args:
        time_period: Natural language time period (e.g., 'last 3 months', 'this year')
        top_categories: Number of top categories to analyze (1-50)

    Returns:
        Expense analysis with category breakdown and insights
    """
    logger.info(f"📊 Analyzing expenses by category for '{time_period}'")

    try:
        # Get database manager
        db_manager = await get_db_manager()

        try:
            # Use transaction service directly
            transaction_service = TransactionService(db_manager)
            date_range = parse_natural_language_date(time_period)
            analysis_data = await transaction_service.get_expense_summary(
                start_date=date_range.start_date,
                end_date=date_range.end_date,
                group_by="category",
            )

            # Format for response
            formatted_categories = [
                {
                    "category_name": category.category_name,
                    "total_amount": float(category.total_amount),
                    "transaction_count": category.transaction_count,
                    "percentage_of_total": category.percentage_of_total,
                    "average_amount": float(category.average_amount),
                }
                for category in analysis_data["category_breakdown"][:top_categories]
            ]

            analysis_data = {
                "analysis_period": f"{date_range.start_date.strftime('%Y-%m-%d')} to {date_range.end_date.strftime('%Y-%m-%d')}",
                "total_expenses": float(analysis_data["total_expenses"]),
                "currency": analysis_data["currency"],
                "top_categories": formatted_categories,
            }

            return ExpenseAnalysisResponse(**analysis_data)
        finally:
            await db_manager.close()

    except Exception as e:
        logger.error(f"❌ Failed to analyze expenses: {e}")
        raise RuntimeError(f"Failed to analyze expenses by category: {e!s}") from e


@mcp.tool()
async def analyze_income_vs_expenses(
    time_period: str = "last 3 months",
) -> IncomeVsExpensesResponse:
    """
    Analyze income vs expenses to understand savings rate and financial health.

    Args:
        time_period: Natural language time period (e.g., 'last 3 months', 'this year')

    Returns:
        Income vs expense analysis with savings insights
    """
    logger.info(f"💰 Analyzing income vs expenses for '{time_period}'")

    try:
        # Get database manager
        db_manager = await get_db_manager()

        try:
            # Use transaction service directly
            transaction_service = TransactionService(db_manager)
            date_range = parse_natural_language_date(time_period)
            income_expense_analysis = await transaction_service.get_income_vs_expense(
                start_date=date_range.start_date, end_date=date_range.end_date
            )

            # Format for response
            from .models.responses import (
                FinancialOverviewResponse,
                SavingsAnalysisResponse,
            )

            financial_overview = FinancialOverviewResponse(
                total_income=f"{float(income_expense_analysis.total_income):.2f} {income_expense_analysis.currency}",
                total_expenses=f"{float(income_expense_analysis.total_expenses):.2f} {income_expense_analysis.currency}",
                net_savings=f"{float(income_expense_analysis.net_savings):.2f} {income_expense_analysis.currency}",
                savings_rate=f"{income_expense_analysis.savings_rate:.1f}%",
                currency=income_expense_analysis.currency,
            )

            savings_analysis = SavingsAnalysisResponse(
                status="positive"
                if income_expense_analysis.net_savings > 0
                else "negative",
                monthly_savings=f"{float(income_expense_analysis.net_savings):.2f} {income_expense_analysis.currency}",
                recommendations=["Continue current savings habits"]
                if income_expense_analysis.net_savings > 0
                else ["Review expenses to improve savings"],
            )

            expense_breakdown = [
                {
                    "category_name": cat.category_name,
                    "total_amount": float(cat.total_amount),
                    "percentage_of_total": cat.percentage_of_total,
                }
                for cat in income_expense_analysis.expense_breakdown[:10]
            ]

            return IncomeVsExpensesResponse(
                analysis_period=f"{date_range.start_date.strftime('%Y-%m-%d')} to {date_range.end_date.strftime('%Y-%m-%d')}",
                financial_overview=financial_overview,
                expense_breakdown=expense_breakdown,
                savings_analysis=savings_analysis,
            )
        finally:
            await db_manager.close()

    except Exception as e:
        logger.error(f"❌ Failed to analyze income vs expenses: {e}")
        raise RuntimeError(f"Failed to analyze income vs expenses: {e!s}") from e


@mcp.tool()
async def get_savings_recommendations(
    time_period: str = "last 3 months", target_savings_rate: float = 20.0
) -> SavingsOptimizationResponse:
    """
    Get personalized savings optimization recommendations.

    Args:
        time_period: Natural language time period for analysis
            (e.g., 'last 3 months', 'this year')
        target_savings_rate: Target savings rate percentage (default 20%)

    Returns:
        Comprehensive savings recommendations with actionable insights
    """
    logger.info(
        f"💡 Generating savings recommendations for '{time_period}' "
        f"with {target_savings_rate}% target"
    )

    try:
        # Get database manager
        db_manager = await get_db_manager()

        try:
            from .services.savings_service import SavingsService
            from .utils.date_utils import parse_natural_language_date

            # Parse time period
            date_range = parse_natural_language_date(time_period)

            # Initialize savings service
            savings_service = SavingsService(db_manager)

            # Get recommendations
            recommendations_data = await savings_service.get_savings_recommendations(
                start_date=date_range.start_date,
                end_date=date_range.end_date,
                target_savings_rate=target_savings_rate,
            )

            return SavingsOptimizationResponse(**recommendations_data)
        finally:
            await db_manager.close()

    except Exception as e:
        logger.error(f"❌ Failed to generate savings recommendations: {e}")
        raise RuntimeError(f"Failed to generate savings recommendations: {e!s}") from e


@mcp.tool()
async def analyze_spending_trends(
    months: int = 6, category: str | None = None
) -> SpendingTrendResponse:
    """
    Analyze spending trends over time to identify patterns.

    Args:
        months: Number of months to analyze (1-24)
        category: Optional specific category to analyze

    Returns:
        Spending trend analysis with projections and insights
    """
    logger.info(
        f"📈 Analyzing spending trends for {months} months"
        + (f" in {category}" if category else "")
    )

    try:
        # Get database manager
        db_manager = await get_db_manager()

        try:
            from .services.trend_service import TrendService

            # Initialize trend service
            trend_service = TrendService(db_manager)

            # Get trend analysis
            trend_data = await trend_service.analyze_spending_trends(
                months=months, category=category
            )

            return SpendingTrendResponse(**trend_data)
        finally:
            await db_manager.close()

    except Exception as e:
        logger.error(f"❌ Failed to analyze spending trends: {e}")
        raise RuntimeError(f"Failed to analyze spending trends: {e!s}") from e


@mcp.tool()
async def analyze_category_trends(
    months: int = 6, top_n: int = 5
) -> CategoryTrendsResponse:
    """
    Analyze spending trends by category to identify growth patterns.

    Args:
        months: Number of months to analyze (1-24)
        top_n: Number of top categories to analyze (1-20)

    Returns:
        Category trend analysis with comparative insights
    """
    logger.info(
        f"📊 Analyzing category trends for top {top_n} categories over {months} months"
    )

    try:
        # Get database manager
        db_manager = await get_db_manager()

        try:
            from .services.trend_service import TrendService

            # Initialize trend service
            trend_service = TrendService(db_manager)

            # Get category trends
            trend_data = await trend_service.analyze_category_trends(
                months=months, top_n=top_n
            )

            return CategoryTrendsResponse(**trend_data)
        finally:
            await db_manager.close()

    except Exception as e:
        logger.error(f"❌ Failed to analyze category trends: {e}")
        raise RuntimeError(f"Failed to analyze category trends: {e!s}") from e


@mcp.tool()
async def analyze_income_expense_trends(
    months: int = 12,
) -> IncomeVsExpenseTrendsResponse:
    """
    Analyze income vs expense trends to track financial health over time.

    Args:
        months: Number of months to analyze (3-24)

    Returns:
        Income vs expense trend analysis with sustainability insights
    """
    logger.info(f"💹 Analyzing income vs expense trends for {months} months")

    try:
        # Get database manager
        db_manager = await get_db_manager()

        try:
            from .services.trend_service import TrendService

            # Initialize trend service
            trend_service = TrendService(db_manager)

            # Get income vs expense trends
            trend_data = await trend_service.analyze_income_vs_expense_trends(
                months=months
            )

            return IncomeVsExpenseTrendsResponse(**trend_data)
        finally:
            await db_manager.close()

    except Exception as e:
        logger.error(f"❌ Failed to analyze income vs expense trends: {e}")
        raise RuntimeError(f"Failed to analyze income vs expense trends: {e!s}") from e


def main() -> int:
    """Main entry point for the MCP server."""
    try:
        logger.info("🎯 MoneyWiz MCP Server starting with FastMCP")

        # Initialize database connection for the context
        config = Config.from_env()
        logger.info(f"📊 Database: {config.database_path}")
        logger.info(f"🔒 Read-only mode: {config.read_only}")

        # Validate database exists
        if not Path(config.database_path).exists():
            error_msg = f"MoneyWiz database not found at: {config.database_path}"
            logger.error(f"❌ {error_msg}")
            return 1

        # Store config for tools to use
        mcp._config = config

        # FastMCP handles its own event loop - just call run() directly
        mcp.run()
        return 0

    except KeyboardInterrupt:
        logger.info("⏹️ Server shutdown requested")
        return 0
    except Exception as e:
        logger.error(f"💥 Server error: {e}")
        return 1


def cli_main() -> None:
    """CLI entry point."""
    sys.exit(main())


if __name__ == "__main__":
    cli_main()
