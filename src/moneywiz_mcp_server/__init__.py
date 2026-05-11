"""MoneyWiz MCP Server - A Model Context Protocol server for MoneyWiz financial data.

This package provides MCP tools for accessing MoneyWiz SQLite database,
enabling AI assistants to perform financial analysis and transaction management.
"""

from importlib.metadata import PackageNotFoundError, version

__author__ = "Juan Carlos Valerio Arrieta"
__email__ = "jcvalerio@gmail.com"

try:
    __version__ = version("moneywiz-mcp-server")
except PackageNotFoundError:  # pragma: no cover - only possible outside installs
    __version__ = "0.0.0"

# Re-export main components for easier imports
from .config import Config

__all__ = ["Config", "__version__"]
