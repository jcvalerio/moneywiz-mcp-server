#!/usr/bin/env python3
"""MoneyWiz MCP Server - Modern FastMCP implementation."""

import logging
import os
import sys
from typing import Optional, List

from mcp.server import FastMCP
from .database.connection import DatabaseManager
from .config import Config
from .models.responses import (
    AccountListResponse, 
    AccountDetailResponse,
    AccountResponse,
    TransactionListResponse,
    ExpenseAnalysisResponse,
    IncomeVsExpensesResponse
)
from .models.savings_responses import (
    SavingsOptimizationResponse,
    SpendingTrendResponse,
    CategoryTrendsResponse,
    IncomeVsExpenseTrendsResponse
)
from .utils.env_loader import load_env_file

# Configure logging to stderr (MCP best practice)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
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
    include_hidden: bool = False,
    account_type: Optional[str] = None
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
            # Import here to avoid circular imports
            from .tools.accounts import list_accounts_tool
            
            # Create tool instance and get results
            tool = list_accounts_tool(db_manager)
            accounts_data = await tool.handler(
                include_hidden=include_hidden,
                account_type=account_type
            )
            
            # Convert to structured response
            accounts = [AccountResponse(**account) for account in accounts_data]
            
            return AccountListResponse(
                accounts=accounts,
                total_count=len(accounts),
                filters_applied={
                    "include_hidden": include_hidden,
                    "account_type": account_type
                }
            )
        finally:
            await db_manager.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to list accounts: {e}")
        raise RuntimeError(f"Failed to retrieve accounts: {str(e)}")


@mcp.tool()
async def get_account(
    account_id: str,
    include_transactions: bool = False
) -> AccountDetailResponse:
    """
    Get detailed information about a specific account.
    
    Args:
        account_id: Unique identifier for the account
        include_transactions: Include recent transactions in response
    
    Returns:
        Detailed account information with optional transactions
    """
    logger.info(f"🔍 Getting account {account_id} (transactions={include_transactions})")
    
    try:
        # Get database manager
        db_manager = await get_db_manager()
        
        try:
            from .tools.accounts import get_account_tool
            
            tool = get_account_tool(db_manager)
            account_data = await tool.handler(
                account_id=account_id,
                include_transactions=include_transactions
            )
            
            return AccountDetailResponse(**account_data)
        finally:
            await db_manager.close()
        
    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get account {account_id}: {e}")
        raise RuntimeError(f"Failed to retrieve account details: {str(e)}")


@mcp.tool()
async def search_transactions(
    time_period: str = "last 3 months",
    account_ids: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    transaction_type: Optional[str] = None,
    limit: int = 100
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
            from .tools.transactions import search_transactions_tool
            from .utils.date_utils import parse_natural_language_date, format_date_range_for_display
            
            # Parse the time period for metadata
            date_range = parse_natural_language_date(time_period)
            
            tool = search_transactions_tool(db_manager)
            transactions_data = await tool.handler(
                time_period=time_period,
                account_ids=account_ids,
                categories=categories,
                transaction_type=transaction_type,
                limit=limit
            )
            
            return TransactionListResponse(
                transactions=transactions_data,
                total_count=len(transactions_data),
                date_range=format_date_range_for_display(date_range),
                filters_applied={
                    "time_period": time_period,
                    "account_ids": account_ids,
                    "categories": categories,
                    "transaction_type": transaction_type,
                    "limit": limit
                }
            )
        finally:
            await db_manager.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to search transactions: {e}")
        raise RuntimeError(f"Failed to search transactions: {str(e)}")


@mcp.tool()
async def analyze_expenses_by_category(
    time_period: str = "last 3 months",
    top_categories: int = 10
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
            from .tools.transactions import analyze_expenses_by_category_tool
            
            tool = analyze_expenses_by_category_tool(db_manager)
            analysis_data = await tool.handler(
                time_period=time_period,
                top_categories=top_categories
            )
            
            return ExpenseAnalysisResponse(**analysis_data)
        finally:
            await db_manager.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to analyze expenses: {e}")
        raise RuntimeError(f"Failed to analyze expenses by category: {str(e)}")


@mcp.tool()
async def analyze_income_vs_expenses(
    time_period: str = "last 3 months"
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
            from .tools.transactions import analyze_income_vs_expenses_tool
            
            tool = analyze_income_vs_expenses_tool(db_manager)
            analysis_data = await tool.handler(time_period=time_period)
            
            return IncomeVsExpensesResponse(**analysis_data)
        finally:
            await db_manager.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to analyze income vs expenses: {e}")
        raise RuntimeError(f"Failed to analyze income vs expenses: {str(e)}")


@mcp.tool()
async def get_savings_recommendations(
    time_period: str = "last 3 months",
    target_savings_rate: float = 20.0
) -> SavingsOptimizationResponse:
    """
    Get personalized savings optimization recommendations.
    
    Args:
        time_period: Natural language time period for analysis (e.g., 'last 3 months', 'this year')
        target_savings_rate: Target savings rate percentage (default 20%)
    
    Returns:
        Comprehensive savings recommendations with actionable insights
    """
    logger.info(f"💡 Generating savings recommendations for '{time_period}' with {target_savings_rate}% target")
    
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
                target_savings_rate=target_savings_rate
            )
            
            return SavingsOptimizationResponse(**recommendations_data)
        finally:
            await db_manager.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to generate savings recommendations: {e}")
        raise RuntimeError(f"Failed to generate savings recommendations: {str(e)}")


@mcp.tool()
async def analyze_spending_trends(
    months: int = 6,
    category: Optional[str] = None
) -> SpendingTrendResponse:
    """
    Analyze spending trends over time to identify patterns.
    
    Args:
        months: Number of months to analyze (1-24)
        category: Optional specific category to analyze
    
    Returns:
        Spending trend analysis with projections and insights
    """
    logger.info(f"📈 Analyzing spending trends for {months} months" + 
                (f" in {category}" if category else ""))
    
    try:
        # Get database manager
        db_manager = await get_db_manager()
        
        try:
            from .services.trend_service import TrendService
            
            # Initialize trend service
            trend_service = TrendService(db_manager)
            
            # Get trend analysis
            trend_data = await trend_service.analyze_spending_trends(
                months=months,
                category=category
            )
            
            return SpendingTrendResponse(**trend_data)
        finally:
            await db_manager.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to analyze spending trends: {e}")
        raise RuntimeError(f"Failed to analyze spending trends: {str(e)}")


@mcp.tool()
async def analyze_category_trends(
    months: int = 6,
    top_n: int = 5
) -> CategoryTrendsResponse:
    """
    Analyze spending trends by category to identify growth patterns.
    
    Args:
        months: Number of months to analyze (1-24)
        top_n: Number of top categories to analyze (1-20)
    
    Returns:
        Category trend analysis with comparative insights
    """
    logger.info(f"📊 Analyzing category trends for top {top_n} categories over {months} months")
    
    try:
        # Get database manager
        db_manager = await get_db_manager()
        
        try:
            from .services.trend_service import TrendService
            
            # Initialize trend service
            trend_service = TrendService(db_manager)
            
            # Get category trends
            trend_data = await trend_service.analyze_category_trends(
                months=months,
                top_n=top_n
            )
            
            return CategoryTrendsResponse(**trend_data)
        finally:
            await db_manager.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to analyze category trends: {e}")
        raise RuntimeError(f"Failed to analyze category trends: {str(e)}")


@mcp.tool()
async def analyze_income_expense_trends(
    months: int = 12
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
        raise RuntimeError(f"Failed to analyze income vs expense trends: {str(e)}")


def main():
    """Main entry point for the MCP server."""
    try:
        logger.info("🎯 MoneyWiz MCP Server starting with FastMCP")
        
        # Initialize database connection for the context
        config = Config.from_env()
        logger.info(f"📊 Database: {config.database_path}")
        logger.info(f"🔒 Read-only mode: {config.read_only}")
        
        # Validate database exists
        if not os.path.exists(config.database_path):
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


def cli_main():
    """CLI entry point."""
    sys.exit(main())


if __name__ == "__main__":
    cli_main()