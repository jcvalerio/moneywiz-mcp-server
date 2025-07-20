#!/usr/bin/env python3
"""MoneyWiz MCP Server - Modern FastMCP implementation."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List

from mcp.server import FastMCP
from pydantic import BaseModel

from .database.connection import DatabaseManager
from .config import Config
from .models.responses import (
    AccountListResponse, 
    AccountDetailResponse,
    AccountResponse,
    TransactionListResponse,
    ExpenseAnalysisResponse,
    IncomeVsExpensesResponse,
    ErrorResponse
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


class ServerContext(BaseModel):
    """Server context for dependency injection."""
    model_config = {"arbitrary_types_allowed": True}
    
    db_manager: DatabaseManager
    config: Config


@asynccontextmanager
async def lifespan():
    """Async context manager for server lifecycle management."""
    logger.info("🚀 Starting MoneyWiz MCP Server")
    
    try:
        # Load configuration
        config = Config.from_env()
        logger.info(f"📊 Database: {config.database_path}")
        logger.info(f"🔒 Read-only mode: {config.read_only}")
        
        # Validate database exists
        if not os.path.exists(config.database_path):
            error_msg = f"MoneyWiz database not found at: {config.database_path}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        # Initialize database connection
        db_manager = DatabaseManager(config.database_path, read_only=config.read_only)
        await db_manager.initialize()
        logger.info("✅ Database connection established")
        
        # Create server context
        context = ServerContext(db_manager=db_manager, config=config)
        
        yield context
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize server: {e}")
        raise
    finally:
        # Cleanup
        try:
            if 'db_manager' in locals():
                await db_manager.close()
                logger.info("🔧 Database connections closed")
        except Exception as e:
            logger.warning(f"⚠️ Error during cleanup: {e}")


# Create FastMCP server instance
mcp = FastMCP("moneywiz-mcp-server", lifespan=lifespan)


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
    
    context: ServerContext = mcp.context
    
    try:
        # Import here to avoid circular imports
        from .tools.accounts import list_accounts_tool
        
        # Create tool instance and get results
        tool = list_accounts_tool(context.db_manager)
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
    
    context: ServerContext = mcp.context
    
    try:
        from .tools.accounts import get_account_tool
        
        tool = get_account_tool(context.db_manager)
        account_data = await tool.handler(
            account_id=account_id,
            include_transactions=include_transactions
        )
        
        return AccountDetailResponse(**account_data)
        
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
    
    context: ServerContext = mcp.context
    
    try:
        from .tools.transactions import search_transactions_tool
        from .utils.date_utils import parse_natural_language_date, format_date_range_for_display
        
        # Parse the time period for metadata
        date_range = parse_natural_language_date(time_period)
        
        tool = search_transactions_tool(context.db_manager)
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
    
    context: ServerContext = mcp.context
    
    try:
        from .tools.transactions import analyze_expenses_by_category_tool
        
        tool = analyze_expenses_by_category_tool(context.db_manager)
        analysis_data = await tool.handler(
            time_period=time_period,
            top_categories=top_categories
        )
        
        return ExpenseAnalysisResponse(**analysis_data)
        
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
    
    context: ServerContext = mcp.context
    
    try:
        from .tools.transactions import analyze_income_vs_expenses_tool
        
        tool = analyze_income_vs_expenses_tool(context.db_manager)
        analysis_data = await tool.handler(time_period=time_period)
        
        return IncomeVsExpensesResponse(**analysis_data)
        
    except Exception as e:
        logger.error(f"❌ Failed to analyze income vs expenses: {e}")
        raise RuntimeError(f"Failed to analyze income vs expenses: {str(e)}")


async def main():
    """Main entry point for the MCP server."""
    try:
        logger.info("🎯 MoneyWiz MCP Server starting with FastMCP")
        await mcp.run()
    except KeyboardInterrupt:
        logger.info("⏹️ Server shutdown requested")
    except Exception as e:
        logger.error(f"💥 Server error: {e}")
        return 1
    return 0


def cli_main():
    """CLI entry point that runs the async main function."""
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


if __name__ == "__main__":
    cli_main()