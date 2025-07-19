"""MoneyWiz MCP Server - A Model Context Protocol server for MoneyWiz financial data.

This package provides MCP tools for accessing MoneyWiz SQLite database,
enabling AI assistants to perform financial analysis and transaction management.
"""

__version__ = "1.0.0"
__author__ = "MoneyWiz MCP Team"
__email__ = "dev@example.com"

# Re-export main components for easier imports
from .config import Config

__all__ = ["Config", "__version__"]