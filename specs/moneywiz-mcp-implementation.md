# MoneyWiz MCP Server - Technical Implementation Guide

## 1. Project Structure (IMPLEMENTED)

```
moneywiz-mcp-server/                    ✅ COMPLETED
├── src/moneywiz_mcp_server/           ✅ Python package structure
│   ├── __init__.py                    ✅ Module setup
│   ├── server.py                      ✅ MCP server with decorator pattern
│   ├── config.py                      ✅ Environment configuration
│   ├── tools/                         ✅ MCP tools package
│   │   ├── __init__.py               ✅ Package init
│   │   ├── accounts.py               ✅ Account tools (WORKING)
│   │   ├── transactions.py           🚧 TODO: Transaction tools
│   │   ├── analytics.py              🚧 TODO: Analysis tools
│   │   └── categories.py             🚧 TODO: Category management
│   ├── database/                      ✅ Database layer
│   │   ├── __init__.py               ✅ Package init
│   │   └── connection.py             ✅ DatabaseManager with Core Data
│   └── utils/                         ✅ Utilities package
│       ├── __init__.py               ✅ Package init
│       ├── validators.py             ✅ Input validation
│       └── formatters.py             ✅ Output formatting
├── tests/                             ✅ Test framework
│   ├── __init__.py                   ✅ Package init
│   ├── test_accounts.py              ✅ Account tool tests
│   └── fixtures/                     ✅ Test data
├── specs/                             ✅ Documentation
│   ├── moneywiz-mcp-prd.md          ✅ Requirements
│   ├── moneywiz-mcp-implementation.md ✅ This guide
│   └── implementation-status.md      ✅ Current status
├── pyproject.toml                     ✅ Modern Python packaging
├── SETUP.md                           ✅ Installation guide
├── .env.example                       ✅ Environment template
├── claude_desktop_config.json         ✅ Claude Desktop config
├── test_mcp_connection.py             ✅ Comprehensive test script
└── continue-development.py            ✅ Development continuation script
```

## 🎯 IMPLEMENTATION STATUS UPDATE

### ✅ FULLY WORKING (Ready for Use)
- **MCP Server**: Functional with real MoneyWiz database
- **Account Tools**: Lists 52 real accounts, get account details
- **Claude Desktop**: Integrated and tested
- **Database**: Direct Core Data SQLite access (bypasses moneywiz-api issues)

### 🚧 NEXT PRIORITIES
- **Transaction Tools**: Entity mapping in progress
- **Analytics**: Depends on transaction implementation
- **Categories**: Core Data entities identified but not implemented

## 2. Core Implementation

### 2.1 Main Server (server.py)

```python
#!/usr/bin/env python3
"""MoneyWiz MCP Server - Main entry point"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .database.connection import DatabaseManager
from .tools import (
    list_accounts_tool,
    get_account_tool,
    search_transactions_tool,
    create_transaction_tool,
    analyze_spending_tool,
    analyze_cash_flow_tool
)
from .config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MoneyWizMCPServer:
    """Main MCP server for MoneyWiz integration"""
    
    def __init__(self, config: Config):
        self.config = config
        self.server = Server("moneywiz-mcp-server")
        self.db_manager = DatabaseManager(config.database_path)
        self._setup_tools()
        
    def _setup_tools(self):
        """Register all available tools"""
        # Account tools
        self.server.add_tool(list_accounts_tool(self.db_manager))
        self.server.add_tool(get_account_tool(self.db_manager))
        
        # Transaction tools
        self.server.add_tool(search_transactions_tool(self.db_manager))
        self.server.add_tool(create_transaction_tool(self.db_manager))
        
        # Analytics tools
        self.server.add_tool(analyze_spending_tool(self.db_manager))
        self.server.add_tool(analyze_cash_flow_tool(self.db_manager))
        
        logger.info(f"Registered {len(self.server.tools)} tools")
    
    async def run(self):
        """Run the MCP server"""
        logger.info("Starting MoneyWiz MCP Server...")
        
        # Initialize database connection
        await self.db_manager.initialize()
        
        try:
            # Run the stdio server
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    server_info={
                        "name": "moneywiz-mcp-server",
                        "version": "1.0.0",
                        "description": "MCP server for MoneyWiz financial data"
                    }
                )
        finally:
            await self.db_manager.close()

async def main():
    """Main entry point"""
    # Load configuration
    config = Config.from_env()
    
    # Validate database path
    if not os.path.exists(config.database_path):
        logger.error(f"Database not found at {config.database_path}")
        return 1
    
    # Create and run server
    server = MoneyWizMCPServer(config)
    await server.run()
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
```

### 2.2 Database Connection (database/connection.py)

```python
"""Database connection management for MoneyWiz SQLite database"""

import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from moneywiz_api import MoneywizApi
import aiosqlite

class DatabaseManager:
    """Manages connections to MoneyWiz SQLite database"""
    
    def __init__(self, db_path: str, read_only: bool = True):
        self.db_path = Path(db_path)
        self.read_only = read_only
        self._api: Optional[MoneywizApi] = None
        self._connection: Optional[aiosqlite.Connection] = None
        
    async def initialize(self):
        """Initialize database connections"""
        # Initialize moneywiz-api
        self._api = MoneywizApi(str(self.db_path))
        
        # Initialize async SQLite connection for custom queries
        uri = f"file:{self.db_path}?mode=ro" if self.read_only else str(self.db_path)
        self._connection = await aiosqlite.connect(uri, uri=True)
        
    async def close(self):
        """Close database connections"""
        if self._connection:
            await self._connection.close()
            
    @property
    def api(self) -> MoneywizApi:
        """Get MoneywizApi instance"""
        if not self._api:
            raise RuntimeError("Database not initialized")
        return self._api
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions"""
        if self.read_only:
            raise RuntimeError("Cannot start transaction in read-only mode")
            
        async with self._connection.execute("BEGIN"):
            try:
                yield self._connection
                await self._connection.commit()
            except Exception:
                await self._connection.rollback()
                raise
    
    async def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as dictionaries"""
        async with self._connection.execute(query, params or ()) as cursor:
            columns = [description[0] for description in cursor.description]
            rows = await cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
```

### 2.3 Account Tools (tools/accounts.py)

```python
"""Account-related MCP tools"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp.types import Tool, TextContent

from ..database.connection import DatabaseManager
from ..utils.validators import validate_account_type
from ..utils.formatters import format_currency

def list_accounts_tool(db_manager: DatabaseManager) -> Tool:
    """Create the list_accounts tool"""
    
    async def handler(
        include_hidden: bool = False,
        account_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all accounts with balances"""
        
        # Get all accounts using moneywiz-api
        accounts = db_manager.api.account_manager.get_all_accounts()
        
        # Filter accounts
        result = []
        for account in accounts:
            # Skip hidden accounts if requested
            if not include_hidden and account.get('hidden', False):
                continue
                
            # Filter by type if specified
            if account_type and account.get('type') != account_type:
                continue
            
            # Format account data
            result.append({
                "id": account['id'],
                "name": account['name'],
                "type": account.get('type', 'unknown'),
                "balance": format_currency(
                    account.get('balance', 0),
                    account.get('currency', 'USD')
                ),
                "currency": account.get('currency', 'USD'),
                "last_updated": datetime.now().isoformat()
            })
        
        return result
    
    return Tool(
        name="list_accounts",
        description="List all MoneyWiz accounts with current balances",
        parameters={
            "type": "object",
            "properties": {
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden accounts",
                    "default": False
                },
                "account_type": {
                    "type": "string",
                    "description": "Filter by account type",
                    "enum": ["checking", "savings", "credit_card", "investment", "cash"]
                }
            }
        },
        handler=handler
    )

def get_account_tool(db_manager: DatabaseManager) -> Tool:
    """Create the get_account tool"""
    
    async def handler(
        account_id: str,
        include_transactions: bool = False
    ) -> Dict[str, Any]:
        """Get detailed information about a specific account"""
        
        # Get account details
        account = db_manager.api.account_manager.get_account(account_id)
        
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        result = {
            "id": account['id'],
            "name": account['name'],
            "type": account.get('type', 'unknown'),
            "balance": format_currency(
                account.get('balance', 0),
                account.get('currency', 'USD')
            ),
            "currency": account.get('currency', 'USD'),
            "created_date": account.get('created_date', ''),
            "institution": account.get('institution', ''),
            "account_number_ending": account.get('account_number_ending', '')
        }
        
        # Optionally include recent transactions
        if include_transactions:
            transactions = db_manager.api.transaction_manager.get_transactions_for_account(
                account_id,
                limit=10
            )
            result['recent_transactions'] = [
                {
                    "id": t['id'],
                    "date": t['date'],
                    "amount": format_currency(t['amount'], account.get('currency', 'USD')),
                    "payee": t.get('payee', ''),
                    "category": t.get('category', '')
                }
                for t in transactions
            ]
        
        return result
    
    return Tool(
        name="get_account",
        description="Get detailed information about a specific account",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "The account ID"
                },
                "include_transactions": {
                    "type": "boolean",
                    "description": "Include recent transactions",
                    "default": False
                }
            },
            "required": ["account_id"]
        },
        handler=handler
    )
```

### 2.4 Transaction Tools (tools/transactions.py)

```python
"""Transaction-related MCP tools"""

from datetime import datetime, date
from typing import Any, Dict, List, Optional

from mcp.types import Tool

from ..database.connection import DatabaseManager
from ..utils.validators import validate_transaction_type, validate_amount
from ..utils.formatters import format_currency, parse_date

def search_transactions_tool(db_manager: DatabaseManager) -> Tool:
    """Create the search_transactions tool"""
    
    async def handler(
        account_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        category: Optional[str] = None,
        payee: Optional[str] = None,
        description: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search transactions with various filters"""
        
        # Build query
        query = """
        SELECT t.*, a.name as account_name, a.currency
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE 1=1
        """
        params = []
        
        if account_id:
            query += " AND t.account_id = ?"
            params.append(account_id)
            
        if start_date:
            query += " AND t.date >= ?"
            params.append(parse_date(start_date).isoformat())
            
        if end_date:
            query += " AND t.date <= ?"
            params.append(parse_date(end_date).isoformat())
            
        if min_amount is not None:
            query += " AND ABS(t.amount) >= ?"
            params.append(abs(min_amount))
            
        if max_amount is not None:
            query += " AND ABS(t.amount) <= ?"
            params.append(abs(max_amount))
            
        if category:
            query += " AND t.category LIKE ?"
            params.append(f"%{category}%")
            
        if payee:
            query += " AND t.payee LIKE ?"
            params.append(f"%{payee}%")
            
        if description:
            query += " AND t.description LIKE ?"
            params.append(f"%{description}%")
            
        query += f" ORDER BY t.date DESC LIMIT {limit}"
        
        # Execute query
        transactions = await db_manager.execute_query(query, tuple(params))
        
        # Format results
        return [
            {
                "id": t['id'],
                "date": t['date'],
                "amount": format_currency(t['amount'], t['currency']),
                "category": t.get('category', ''),
                "payee": t.get('payee', ''),
                "description": t.get('description', ''),
                "account": t['account_name'],
                "type": "expense" if t['amount'] < 0 else "income"
            }
            for t in transactions
        ]
    
    return Tool(
        name="search_transactions",
        description="Search transactions with various filters",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Filter by account ID"},
                "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "min_amount": {"type": "number", "description": "Minimum amount"},
                "max_amount": {"type": "number", "description": "Maximum amount"},
                "category": {"type": "string", "description": "Filter by category"},
                "payee": {"type": "string", "description": "Filter by payee"},
                "description": {"type": "string", "description": "Search in description"},
                "limit": {"type": "integer", "description": "Maximum results", "default": 100}
            }
        },
        handler=handler
    )

def create_transaction_tool(db_manager: DatabaseManager) -> Tool:
    """Create the create_transaction tool"""
    
    async def handler(
        account_id: str,
        amount: float,
        date: str,
        category: str,
        payee: Optional[str] = None,
        description: Optional[str] = None,
        type: str = "expense"
    ) -> Dict[str, Any]:
        """Create a new transaction"""
        
        # Validate inputs
        validate_transaction_type(type)
        validate_amount(amount, type)
        transaction_date = parse_date(date)
        
        # Adjust amount based on type
        if type == "expense" and amount > 0:
            amount = -amount
        elif type == "income" and amount < 0:
            amount = abs(amount)
        
        # Create transaction using moneywiz-api
        transaction_data = {
            "account_id": account_id,
            "amount": amount,
            "date": transaction_date.isoformat(),
            "category": category,
            "payee": payee or "",
            "description": description or "",
            "cleared": False
        }
        
        # Note: Actual implementation would use moneywiz-api transaction creation
        # For now, we'll return a success response
        # transaction_id = db_manager.api.transaction_manager.create_transaction(transaction_data)
        
        return {
            "id": "mock_transaction_id",
            "success": True,
            "message": f"Created {type} transaction for {format_currency(abs(amount), 'USD')}"
        }
    
    return Tool(
        name="create_transaction",
        description="Create a new transaction in MoneyWiz",
        parameters={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Account ID"},
                "amount": {"type": "number", "description": "Transaction amount"},
                "date": {"type": "string", "description": "Transaction date (YYYY-MM-DD)"},
                "category": {"type": "string", "description": "Category name"},
                "payee": {"type": "string", "description": "Payee name"},
                "description": {"type": "string", "description": "Transaction description"},
                "type": {
                    "type": "string",
                    "description": "Transaction type",
                    "enum": ["expense", "income", "transfer"]
                }
            },
            "required": ["account_id", "amount", "date", "category", "type"]
        },
        handler=handler
    )
```

### 2.5 Analytics Tools (tools/analytics.py)

```python
"""Financial analytics MCP tools"""

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict

from mcp.types import Tool

from ..database.connection import DatabaseManager
from ..utils.formatters import format_currency, parse_date

def analyze_spending_tool(db_manager: DatabaseManager) -> Tool:
    """Create the analyze_spending_by_category tool"""
    
    async def handler(
        start_date: str,
        end_date: str,
        account_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Analyze spending by category for a date range"""
        
        # Build query
        query = """
        SELECT 
            c.name as category,
            c.parent_category,
            SUM(ABS(t.amount)) as total_amount,
            COUNT(t.id) as transaction_count,
            a.currency
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        JOIN categories c ON t.category_id = c.id
        WHERE t.amount < 0  -- Only expenses
        AND t.date >= ? AND t.date <= ?
        """
        
        params = [parse_date(start_date).isoformat(), parse_date(end_date).isoformat()]
        
        if account_ids:
            placeholders = ','.join(['?' for _ in account_ids])
            query += f" AND t.account_id IN ({placeholders})"
            params.extend(account_ids)
        
        query += " GROUP BY c.name, c.parent_category, a.currency ORDER BY total_amount DESC"
        
        # Execute query
        results = await db_manager.execute_query(query, tuple(params))
        
        # Calculate total for percentages
        total_spending = sum(r['total_amount'] for r in results)
        
        # Format results
        categories = []
        for row in results:
            categories.append({
                "category": row['category'],
                "parent_category": row['parent_category'] or None,
                "total_amount": format_currency(row['total_amount'], row['currency']),
                "transaction_count": row['transaction_count'],
                "percentage": round((row['total_amount'] / total_spending) * 100, 2) if total_spending > 0 else 0
            })
        
        return categories
    
    return Tool(
        name="analyze_spending_by_category",
        description="Analyze spending patterns by category",
        parameters={
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "account_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of account IDs to include"
                }
            },
            "required": ["start_date", "end_date"]
        },
        handler=handler
    )

def analyze_cash_flow_tool(db_manager: DatabaseManager) -> Tool:
    """Create the analyze_cash_flow tool"""
    
    async def handler(
        period: str,
        start_date: str,
        end_date: str,
        account_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Analyze cash flow over time"""
        
        # Determine date format based on period
        date_formats = {
            "daily": "%Y-%m-%d",
            "weekly": "%Y-W%W",
            "monthly": "%Y-%m",
            "yearly": "%Y"
        }
        
        if period not in date_formats:
            raise ValueError(f"Invalid period: {period}")
        
        date_format = date_formats[period]
        
        # Build query
        query = f"""
        SELECT 
            strftime('{date_format}', t.date) as period,
            SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) as income,
            SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as expenses,
            a.currency
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE t.date >= ? AND t.date <= ?
        """
        
        params = [parse_date(start_date).isoformat(), parse_date(end_date).isoformat()]
        
        if account_ids:
            placeholders = ','.join(['?' for _ in account_ids])
            query += f" AND t.account_id IN ({placeholders})"
            params.extend(account_ids)
        
        query += f" GROUP BY period, a.currency ORDER BY period"
        
        # Execute query
        results = await db_manager.execute_query(query, tuple(params))
        
        # Format results with running balance
        cash_flow = []
        running_balance = 0
        
        for row in results:
            net_flow = row['income'] - row['expenses']
            running_balance += net_flow
            
            cash_flow.append({
                "period": row['period'],
                "income": format_currency(row['income'], row['currency']),
                "expenses": format_currency(row['expenses'], row['currency']),
                "net_flow": format_currency(net_flow, row['currency']),
                "running_balance": format_currency(running_balance, row['currency'])
            })
        
        return cash_flow
    
    return Tool(
        name="analyze_cash_flow",
        description="Analyze income vs expenses over time",
        parameters={
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Time period granularity",
                    "enum": ["daily", "weekly", "monthly", "yearly"]
                },
                "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "account_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of account IDs to include"
                }
            },
            "required": ["period", "start_date", "end_date"]
        },
        handler=handler
    )
```

### 2.6 Configuration (config.py)

```python
"""Configuration management for MoneyWiz MCP Server"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

@dataclass
class Config:
    """Server configuration"""
    database_path: str
    read_only: bool = True
    cache_ttl: int = 300  # 5 minutes
    max_results: int = 1000
    backup_before_write: bool = True
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables"""
        # Get database path
        db_path = os.getenv('MONEYWIZ_DB_PATH')
        
        # Try common locations if not specified
        if not db_path:
            possible_paths = [
                # macOS locations
                Path.home() / "Library/Containers/com.moneywiz.personalfinance/Data/Documents/.AppData",
                Path.home() / "Library/Containers/com.moneywiz.mac/Data/Library/Containers/com.moneywiz.mac/Data",
                # Windows locations
                Path.home() / "AppData/Local/SilverWiz/MoneyWiz",
                # Linux locations
                Path.home() / ".config/MoneyWiz"
            ]
            
            for path in possible_paths:
                if path.exists():
                    # Look for SQLite files
                    for db_file in path.glob("*.sqlite"):
                        db_path = str(db_file)
                        break
                if db_path:
                    break
        
        if not db_path:
            raise ValueError(
                "MoneyWiz database not found. Please set MONEYWIZ_DB_PATH environment variable."
            )
        
        return cls(
            database_path=db_path,
            read_only=os.getenv('MONEYWIZ_READ_ONLY', 'true').lower() == 'true',
            cache_ttl=int(os.getenv('CACHE_TTL', '300')),
            max_results=int(os.getenv('MAX_RESULTS', '1000')),
            backup_before_write=os.getenv('BACKUP_BEFORE_WRITE', 'true').lower() == 'true'
        )
```

### 2.7 MCP Configuration (claude_mcp_config.json)

```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "python",
      "args": ["-m", "moneywiz_mcp_server"],
      "env": {
        "MONEYWIZ_DB_PATH": "/path/to/your/moneywiz.sqlite",
        "MONEYWIZ_READ_ONLY": "false"
      }
    }
  }
}
```

### 2.8 Setup Instructions (setup.py)

```python
"""Setup script for MoneyWiz MCP Server"""

from setuptools import setup, find_packages

setup(
    name="moneywiz-mcp-server",
    version="1.0.0",
    description="MCP server for MoneyWiz financial data",
    author="Your Name",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        "mcp[cli]>=1.0.0",
        "moneywiz-api>=0.1.0",
        "aiosqlite>=0.19.0",
        "pandas>=2.0.0",
        "python-dateutil>=2.8.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0"
    ],
    entry_points={
        "console_scripts": [
            "moneywiz-mcp-server=moneywiz_mcp_server.server:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
```

## 3. Installation and Usage

### 3.1 Installation Steps

```bash
# Clone the repository
git clone https://github.com/yourusername/moneywiz-mcp-server.git
cd moneywiz-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Copy environment example
cp .env.example .env
# Edit .env with your MoneyWiz database path

# Test the server
python -m moneywiz_mcp_server
```

### 3.2 Claude Desktop Configuration

1. Locate Claude Desktop configuration:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the MoneyWiz server configuration:

```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "moneywiz_mcp_server"],
      "env": {
        "MONEYWIZ_DB_PATH": "/path/to/your/moneywiz.sqlite"
      }
    }
  }
}
```

3. Restart Claude Desktop

## 4. Usage Examples

### 4.1 Basic Queries

```
User: "Show me all my accounts"
Claude: I'll help you view all your MoneyWiz accounts.

[Uses list_accounts tool]

Here are your accounts:
1. Checking - Chase: $5,234.56
2. Savings - Ally: $15,678.90
3. Credit Card - Amex: -$1,234.00
4. Investment - Vanguard: $45,678.90

Total Net Worth: $65,358.36
```

### 4.2 Transaction Analysis

```
User: "What did I spend on dining out last month?"
Claude: I'll analyze your dining expenses for last month.

[Uses search_transactions and analyze_spending tools]

Your dining out expenses for October 2024:
- Total spent: $567.89
- Number of transactions: 23
- Average per transaction: $24.69
- Percentage of total spending: 12.3%

Top restaurants:
1. Chipotle: $89.45 (8 visits)
2. Starbucks: $67.23 (12 visits)
3. Local Pizza Place: $45.00 (2 visits)
```

### 4.3 Financial Insights

```
User: "How has my cash flow been over the past 3 months?"
Claude: I'll analyze your cash flow for the past 3 months.

[Uses analyze_cash_flow tool]

Cash Flow Summary (Aug-Oct 2024):
- August: Income $5,500, Expenses $4,200, Net +$1,300
- September: Income $5,500, Expenses $4,800, Net +$700
- October: Income $6,200, Expenses $5,100, Net +$1,100

Total: Income $17,200, Expenses $14,100, Net Savings $3,100

Your expenses increased by 21% from August to October, mainly due to:
- Dining out (+$200)
- Shopping (+$350)
- Entertainment (+$150)
```

## 5. Testing

### 5.1 Unit Test Example (tests/test_accounts.py)

```python
"""Tests for account tools"""

import pytest
from unittest.mock import Mock, AsyncMock

from moneywiz_mcp_server.tools.accounts import list_accounts_tool

@pytest.mark.asyncio
async def test_list_accounts():
    """Test listing accounts"""
    # Mock database manager
    db_manager = Mock()
    db_manager.api.account_manager.get_all_accounts.return_value = [
        {
            'id': 'acc1',
            'name': 'Checking',
            'type': 'checking',
            'balance': 1000.00,
            'currency': 'USD',
            'hidden': False
        },
        {
            'id': 'acc2',
            'name': 'Savings',
            'type': 'savings',
            'balance': 5000.00,
            'currency': 'USD',
            'hidden': False
        }
    ]
    
    # Create tool and get handler
    tool = list_accounts_tool(db_manager)
    handler = tool.handler
    
    # Test basic listing
    accounts = await handler()
    assert len(accounts) == 2
    assert accounts[0]['name'] == 'Checking'
    assert accounts[1]['balance'] == '$5,000.00'
    
    # Test filtering by type
    accounts = await handler(account_type='checking')
    assert len(accounts) == 1
    assert accounts[0]['type'] == 'checking'
```

## 6. Security Best Practices

### 6.1 Database Access
- Always use read-only mode by default
- Implement proper SQLite locking
- Validate all inputs to prevent SQL injection
- Never expose database path in error messages

### 6.2 Session Management
- Each MCP session should be isolated
- No persistent state between sessions
- Clear sensitive data after use

### 6.3 Error Handling
- Sanitize error messages
- Log errors securely
- Never expose internal paths or structures

## 7. Performance Optimization

### 7.1 Caching Strategy
- Cache account lists (5-minute TTL)
- Cache category hierarchies
- Invalidate cache on write operations

### 7.2 Query Optimization
- Use indexes for common queries
- Batch operations where possible
- Limit result sets by default

### 7.3 Async Operations
- Use async SQLite for concurrent access
- Implement connection pooling
- Handle backpressure appropriately

## 8. Deployment Considerations

### 8.1 Local Deployment
- Package as standalone executable
- Auto-detect database location
- Provide clear setup instructions

### 8.2 Future Remote Deployment
- Implement authentication layer
- Use secure transport (HTTPS/WSS)
- Add rate limiting
- Implement user isolation

This implementation guide provides a solid foundation for building the MoneyWiz MCP server. The modular architecture allows for easy extension and maintenance while ensuring safety and performance.