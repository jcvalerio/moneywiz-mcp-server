#!/usr/bin/env python3
"""
MoneyWiz MCP Server - Development Continuation Script

This script helps developers quickly resume work on the MoneyWiz MCP server
by setting up the environment and providing a status overview.

Usage:
    python continue-development.py

    # Or make it executable:
    chmod +x continue-development.py
    ./continue-development.py
"""

import asyncio
import importlib.util
import os
from pathlib import Path
import sys

# Optional imports for functionality testing (will be imported conditionally)
try:
    from moneywiz_mcp_server.config import Config
    from moneywiz_mcp_server.database.connection import DatabaseManager
    from moneywiz_mcp_server.tools.accounts import list_accounts_tool

    MONEYWIZ_AVAILABLE = True
except ImportError:
    MONEYWIZ_AVAILABLE = False


def print_banner():
    """Print project banner and status."""
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                        MoneyWiz MCP Server                                  ║
║                      Development Continuation                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    )


def check_environment():
    """Check if the development environment is ready."""
    print("🔍 Checking Development Environment...")

    issues = []

    # Check Python version
    print(f"✅ Python {sys.version.split()[0]}")

    # Check virtual environment
    venv_path = Path("venv")
    if not venv_path.exists():
        issues.append("❌ Virtual environment not found at ./venv")
    else:
        print("✅ Virtual environment found")

    # Check if we're in virtual environment
    if not hasattr(sys, "real_prefix") and not (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        issues.append("❌ Virtual environment not activated")
    else:
        print("✅ Virtual environment activated")

    # Check database path
    db_path = os.getenv("MONEYWIZ_DB_PATH")
    if not db_path:
        issues.append("❌ MONEYWIZ_DB_PATH environment variable not set")
    elif not Path(db_path).exists():
        issues.append(f"❌ Database file not found: {db_path}")
    else:
        size_mb = Path(db_path).stat().st_size / (1024 * 1024)
        print(f"✅ Database found: {size_mb:.1f}MB")

    # Check dependencies
    try:
        # Use importlib.util.find_spec for availability checks
        aiosqlite_spec = importlib.util.find_spec("aiosqlite")
        mcp_spec = importlib.util.find_spec("mcp")
        config_spec = importlib.util.find_spec("moneywiz_mcp_server.config")

        if all([aiosqlite_spec, mcp_spec, config_spec]):
            print("✅ All core dependencies installed")
        else:
            missing = []
            if not aiosqlite_spec:
                missing.append("aiosqlite")
            if not mcp_spec:
                missing.append("mcp")
            if not config_spec:
                missing.append("moneywiz_mcp_server.config")
            issues.append(f"❌ Missing dependencies: {', '.join(missing)}")
    except ImportError as e:
        issues.append(f"❌ Missing dependency: {e}")

    return issues


async def test_functionality():
    """Test current functionality."""
    print("\n🧪 Testing Current Functionality...")

    try:
        # Check if modules are available
        if not MONEYWIZ_AVAILABLE:
            print("❌ MoneyWiz MCP server modules not available")
            return False

        # Test configuration
        config = Config.from_env()
        print(f"✅ Configuration loaded: {Path(config.database_path).name}")

        # Test database connection
        db_manager = DatabaseManager(config.database_path, read_only=config.read_only)
        await db_manager.initialize()
        print("✅ Database connection successful")

        # Test account tools
        tool = list_accounts_tool(db_manager)
        accounts = await tool.handler(include_hidden=False)
        print(f"✅ Account tools working: {len(accounts)} accounts found")

        # Show sample accounts
        if accounts:
            print("   Sample accounts:")
            for i, acc in enumerate(accounts[:3]):
                print(f"     {i + 1}. {acc['name']} ({acc['type']}): {acc['balance']}")

        await db_manager.close()

        return True

    except Exception as e:
        print(f"❌ Functionality test failed: {e}")
        return False


def show_development_status():
    """Show current development status and next steps."""
    print("\n📊 Development Status:")

    status = {
        "✅ COMPLETED": [
            "Core infrastructure (Python, MCP, SQLite)",
            "Database connection with Core Data support",
            "Account tools (list_accounts, get_account)",
            "Claude Desktop integration",
            "Configuration management",
            "Error handling and logging",
        ],
        "🚧 IN PROGRESS": [
            "Transaction tools (search, analytics)",
            "Core Data transaction entity mapping",
            "Advanced filtering and querying",
        ],
        "❌ TODO": [
            "Category management tools",
            "Spending analytics",
            "Cash flow analysis",
            "Payee management",
            "Write operations (when ready)",
        ],
    }

    for section, items in status.items():
        print(f"\n{section}:")
        for item in items:
            print(f"  • {item}")


def show_next_steps():
    """Show immediate next steps for development."""
    print(
        """
🎯 Next Development Steps:

1. ANALYZE TRANSACTION STRUCTURE
   Research Core Data transaction entities (37, 45, 46, 47):

   python -c "
   import asyncio
   from moneywiz_mcp_server.database.connection import DatabaseManager
   from moneywiz_mcp_server.config import Config

   async def research():
       config = Config.from_env()
       db = DatabaseManager(config.database_path)
       await db.initialize()

       # Sample different transaction types
       for entity_id in [37, 45, 46, 47]:
           txns = await db.execute_query(
               'SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? LIMIT 1', (entity_id,)
           )
           if txns:
               print(f'Entity {entity_id} fields:', list(txns[0].keys())[:10])

       await db.close()

   asyncio.run(research())
   "

2. IMPLEMENT TRANSACTION SEARCH
   Create search_transactions_tool in tools/transactions.py:
   - Map Core Data transaction fields to standard format
   - Add date range, amount, and category filtering
   - Handle multiple transaction types

3. ADD TRANSACTION ANALYTICS
   - Spending by category
   - Monthly/weekly patterns
   - Payee analysis

4. TEST WITH CLAUDE DESKTOP
   Restart Claude Desktop and test:
   "Can you show me my MoneyWiz accounts?"
   "Find my largest expenses from last month"

📁 Key Files to Work With:
  • src/moneywiz_mcp_server/tools/accounts.py (working example)
  • src/moneywiz_mcp_server/database/connection.py (Core Data access)
  • specs/implementation-status.md (detailed status)
  • test_mcp_connection.py (comprehensive testing)

🔧 Development Commands:
  • python test_mcp_connection.py  # Test everything
  • pytest tests/ -v              # Run unit tests
  • python -m moneywiz_mcp_server  # Start MCP server
"""
    )


def show_resources():
    """Show available resources and documentation."""
    print(
        """
📚 Resources Available:

📖 Documentation:
  • specs/moneywiz-mcp-prd.md           - Original requirements
  • specs/moneywiz-mcp-implementation.md - Technical guide
  • specs/implementation-status.md       - Current status (NEW)
  • SETUP.md                            - Installation guide

🧪 Testing:
  • test_mcp_connection.py              - Comprehensive test script
  • tests/                              - Unit test suite

⚙️ Configuration:
  • claude_desktop_config.json          - Claude Desktop MCP config
  • .env.example                        - Environment template
  • pyproject.toml                      - Python project config

🗃️ Database Info:
  • Location: {db_path}
  • Core Data entities mapped and documented
  • 52 accounts discovered and accessible
  • Transaction entities identified but not yet implemented

🚀 Quick Start:
  1. Ensure environment variables are set
  2. Run: python test_mcp_connection.py
  3. Start development with transaction entity research
  4. Test changes with Claude Desktop integration
""".format(db_path=os.getenv("MONEYWIZ_DB_PATH", "Not set"))
    )


def main():
    """Main entry point."""
    print_banner()

    # Check environment
    issues = check_environment()

    if issues:
        print(f"\n❌ {len(issues)} issues found:")
        for issue in issues:
            print(f"  {issue}")
        print("\n💡 Fix these issues before continuing development.")
        return 1

    print("✅ Environment check passed!")

    # Test functionality
    if asyncio.run(test_functionality()):
        print("✅ All functionality tests passed!")
    else:
        print("❌ Some functionality tests failed. Check the errors above.")
        return 1

    # Show status and next steps
    show_development_status()
    show_next_steps()
    show_resources()

    print(
        """
🎉 Ready for Development!

The MoneyWiz MCP server is fully functional for account operations.
Next priority: Implement transaction search and analytics tools.

Happy coding! 🚀
"""
    )

    return 0


if __name__ == "__main__":
    # Set up environment variables if not already set
    if not os.getenv("MONEYWIZ_DB_PATH"):
        default_path = (
            "/Users/jcvalerio/Library/Containers/"
            "com.moneywiz.personalfinance-setapp/Data/Documents/.AppData/ipadMoneyWiz.sqlite"
        )
        if Path(default_path).exists():
            os.environ["MONEYWIZ_DB_PATH"] = default_path
            os.environ["MONEYWIZ_READ_ONLY"] = "true"
            print(f"🔧 Auto-set MONEYWIZ_DB_PATH to {default_path}")

    sys.exit(main())
