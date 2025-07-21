#!/usr/bin/env python3
"""Test script to verify MCP server is working correctly."""

import asyncio
import os
import sys

# Add the src directory to the path
sys.path.insert(0, "src")


async def test_mcp_server():
    """Test the MCP server components."""
    print("🧪 Testing MoneyWiz MCP Server...")

    # Test 1: Environment variables
    print("\n1. Environment Variables:")
    db_path = os.environ.get("MONEYWIZ_DB_PATH")
    read_only = os.environ.get("MONEYWIZ_READ_ONLY", "true")

    if db_path:
        print(f"   ✅ MONEYWIZ_DB_PATH: {db_path}")
        if os.path.exists(db_path):
            print("   ✅ Database file exists")
        else:
            print("   ❌ Database file not found")
            return False
    else:
        print("   ❌ MONEYWIZ_DB_PATH not set")
        return False

    print(f"   ✅ MONEYWIZ_READ_ONLY: {read_only}")

    # Test 2: Imports
    print("\n2. Module Imports:")
    try:
        from moneywiz_mcp_server.config import Config
        from moneywiz_mcp_server.database.connection import DatabaseManager
        from moneywiz_mcp_server.tools.accounts import list_accounts_tool

        print("   ✅ All imports successful")
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        return False

    # Test 3: Configuration
    print("\n3. Configuration:")
    try:
        config = Config.from_env()
        print(f"   ✅ Config loaded: {config.database_path}")
        print(f"   ✅ Read-only: {config.read_only}")
    except Exception as e:
        print(f"   ❌ Config error: {e}")
        return False

    # Test 4: Database Connection
    print("\n4. Database Connection:")
    try:
        db_manager = DatabaseManager(config.database_path, read_only=config.read_only)
        await db_manager.initialize()
        print("   ✅ Database connection successful")
        await db_manager.close()
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False

    # Test 5: Account Tools
    print("\n5. Account Tools:")
    try:
        db_manager = DatabaseManager(config.database_path, read_only=config.read_only)
        await db_manager.initialize()

        tool = list_accounts_tool(db_manager)
        accounts = await tool.handler(include_hidden=False)

        print(f"   ✅ Found {len(accounts)} accounts")
        if len(accounts) > 0:
            print(
                f"   ✅ Sample account: {accounts[0]['name']} ({accounts[0]['type']})"
            )

        await db_manager.close()
    except Exception as e:
        print(f"   ❌ Account tools error: {e}")
        return False

    print("\n🎉 All tests passed! MCP server is ready for Claude Desktop.")
    return True


if __name__ == "__main__":
    # Set environment variables for testing
    os.environ["MONEYWIZ_DB_PATH"] = (
        "/Users/jcvalerio/Library/Containers/com.moneywiz.personalfinance-setapp/Data/Documents/.AppData/ipadMoneyWiz.sqlite"
    )
    os.environ["MONEYWIZ_READ_ONLY"] = "true"

    success = asyncio.run(test_mcp_server())
    sys.exit(0 if success else 1)
