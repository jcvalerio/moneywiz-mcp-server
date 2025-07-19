#!/usr/bin/env python3
"""
Minimal MCP server test for Claude Desktop debugging
"""

import asyncio
import json
import sys
import os

# Set environment variables
os.environ["MONEYWIZ_DB_PATH"] = "/Users/jcvalerio/Library/Containers/com.moneywiz.personalfinance-setapp/Data/Documents/.AppData/ipadMoneyWiz.sqlite"
os.environ["MONEYWIZ_READ_ONLY"] = "true"

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create a minimal server
server = Server("moneywiz-test")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="test_connection",
            description="Test MoneyWiz MCP server connection",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "test_connection":
        return [TextContent(type="text", text="✅ MoneyWiz MCP server is working!")]
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Main entry point."""
    try:
        async with stdio_server() as (read_stream, write_stream):
            initialization_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, initialization_options)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)