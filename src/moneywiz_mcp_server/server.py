#!/usr/bin/env python3
"""MoneyWiz MCP Server - Main entry point for the MCP server."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, CallToolResult

from .database.connection import DatabaseManager
from .tools.accounts import list_accounts_tool, get_account_tool
from .tools.transactions import (
    search_transactions_tool,
    analyze_expenses_by_category_tool,
    analyze_income_vs_expenses_tool
)
from .config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)  # Log to stderr to avoid interfering with MCP stdio
    ]
)
logger = logging.getLogger(__name__)


# Global database manager instance
db_manager: Optional[DatabaseManager] = None

# Create server instance
server = Server("moneywiz-mcp-server")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    # Return static tool definitions - don't create instances here
    return [
        Tool(
            name="list_accounts",
            description="List all MoneyWiz accounts with current balances",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Include hidden accounts in results",
                        "default": False
                    },
                    "account_type": {
                        "type": "string",
                        "description": "Filter accounts by type",
                        "enum": ["checking", "savings", "credit_card", "investment", "cash", "loan", "forex"]
                    }
                }
            }
        ),
        Tool(
            name="get_account",
            description="Get detailed information about a specific account",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The unique account identifier"
                    },
                    "include_transactions": {
                        "type": "boolean",
                        "description": "Include recent transactions in response",
                        "default": False
                    }
                },
                "required": ["account_id"]
            }
        ),
        Tool(
            name="search_transactions",
            description="Search and filter transactions with natural language time periods and criteria",
            inputSchema={
                "type": "object",
                "properties": {
                    "time_period": {
                        "type": "string",
                        "description": "Time period in natural language (e.g., 'last 3 months', 'this year')",
                        "default": "last 3 months"
                    },
                    "account_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of account IDs to filter by"
                    },
                    "categories": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "Optional list of category names to filter by"
                    },
                    "transaction_type": {
                        "type": "string",
                        "description": "Optional transaction type filter",
                        "enum": ["deposit", "withdraw", "transfer_in", "transfer_out", "investment_buy", "investment_sell", "refund"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of transactions to return",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000
                    }
                }
            }
        ),
        Tool(
            name="analyze_expenses_by_category",
            description="Analyze expenses by category to identify spending patterns and high-impact categories",
            inputSchema={
                "type": "object",
                "properties": {
                    "time_period": {
                        "type": "string",
                        "description": "Time period in natural language (e.g., 'last 3 months', 'this year')",
                        "default": "last 3 months"
                    },
                    "top_categories": {
                        "type": "integer",
                        "description": "Number of top categories to analyze",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                }
            }
        ),
        Tool(
            name="analyze_income_vs_expenses",
            description="Analyze income vs expenses to understand savings rate and financial health",
            inputSchema={
                "type": "object",
                "properties": {
                    "time_period": {
                        "type": "string",
                        "description": "Time period in natural language (e.g., 'last 3 months', 'this year')",
                        "default": "last 3 months"
                    }
                }
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if not db_manager:
        raise RuntimeError("Database not initialized")
    
    # Create tool instances and call handlers directly
    if name == "list_accounts":
        tool = list_accounts_tool(db_manager)
        result = await tool.handler(
            include_hidden=arguments.get("include_hidden", False),
            account_type=arguments.get("account_type")
        )
        return [TextContent(type="text", text=str(result))]
    
    elif name == "get_account":
        tool = get_account_tool(db_manager)
        result = await tool.handler(
            account_id=arguments["account_id"],
            include_transactions=arguments.get("include_transactions", False)
        )
        return [TextContent(type="text", text=str(result))]
    
    elif name == "search_transactions":
        tool = search_transactions_tool(db_manager)
        result = await tool.handler(
            time_period=arguments.get("time_period", "last 3 months"),
            account_ids=arguments.get("account_ids"),
            categories=arguments.get("categories"),
            transaction_type=arguments.get("transaction_type"),
            limit=arguments.get("limit", 100)
        )
        return [TextContent(type="text", text=str(result))]
    
    elif name == "analyze_expenses_by_category":
        tool = analyze_expenses_by_category_tool(db_manager)
        result = await tool.handler(
            time_period=arguments.get("time_period", "last 3 months"),
            top_categories=arguments.get("top_categories", 10)
        )
        return [TextContent(type="text", text=str(result))]
    
    elif name == "analyze_income_vs_expenses":
        tool = analyze_income_vs_expenses_tool(db_manager)
        result = await tool.handler(
            time_period=arguments.get("time_period", "last 3 months")
        )
        return [TextContent(type="text", text=str(result))]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def run_server(config: Config):
    """Run the MCP server."""
    global db_manager
    
    logger.info(f"Starting MoneyWiz MCP Server")
    logger.info(f"Database: {config.database_path}")
    logger.info(f"Read-only mode: {config.read_only}")
    
    try:
        # Initialize database connection
        db_manager = DatabaseManager(config.database_path, read_only=config.read_only)
        await db_manager.initialize()
        logger.info("Database connection established")
        
        # Run the stdio server
        async with stdio_server() as (read_stream, write_stream):
            logger.info("MCP server listening on stdio")
            
            initialization_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, initialization_options)
            
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        # Clean up database connections
        if db_manager:
            try:
                await db_manager.close()
                logger.info("Database connections closed")
            except Exception as e:
                logger.warning(f"Error closing database: {e}")


async def main():
    """Main entry point for the MCP server."""
    try:
        # Load configuration from environment
        config = Config.from_env()
        
        # Validate database path exists
        if not os.path.exists(config.database_path):
            logger.error(f"MoneyWiz database not found at: {config.database_path}")
            logger.error("Please set MONEYWIZ_DB_PATH environment variable or ensure MoneyWiz is installed")
            return 1
        
        # Run server
        await run_server(config)
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return 1


def cli_main():
    """CLI entry point that runs the async main function."""
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


if __name__ == "__main__":
    cli_main()