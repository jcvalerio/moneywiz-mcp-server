# MoneyWiz MCP Server

A Model Context Protocol (MCP) server that provides AI assistants like Claude with access to MoneyWiz financial data.

## 🎯 Status: PRODUCTION READY (Account Tools)

✅ **Fully functional** account management tools  
✅ **52 real accounts** successfully accessed from MoneyWiz database  
✅ **Real balance calculation** - Fixed $0.00 balance issue  
✅ **Claude Desktop integration** working  
🚧 **Transaction tools** - next development priority  

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Navigate to project
cd /Users/jcvalerio/jcvalerio/dev/github/moneywiz-mcp-server

# Activate virtual environment  
source venv/bin/activate

# Test everything works
python test_mcp_connection.py
```

### 2. Claude Desktop Integration
Your MoneyWiz MCP server is already configured in Claude Desktop! Just:

1. **Restart Claude Desktop** completely (Quit → Reopen)
2. **Test the integration** with: `"Can you show me my MoneyWiz accounts?"`

### 3. Continue Development
```bash
# Get development status and next steps
./continue-development.py

# Or if not executable:
python continue-development.py
```

## 🛠️ What's Working

### Account Tools (100% Complete)
- **`list_accounts`** - Lists all 52 accounts with balances and types
- **`get_account`** - Gets detailed account information by ID
- **Account filtering** - By type (checking, savings, credit card, etc.)
- **Real data** - Connected to your actual MoneyWiz database

### Example Queries
Ask Claude Desktop:
```
"Show me all my MoneyWiz accounts"
"What's the balance of my Scotiabank account?"
"List only my checking accounts from MoneyWiz"
"Get details for my Multimoney $ account"
```

## 🔧 Technical Details

### Architecture
- **MCP Server**: Modern decorator-based tool registration
- **Database**: Direct Core Data SQLite access (bypasses moneywiz-api issues)
- **Safety**: Read-only mode by default
- **Integration**: Seamless Claude Desktop integration

### Database Connection
- **Location**: MoneyWiz Setapp container database
- **Size**: 24.3MB of financial data
- **Entities**: 52 accounts across 7 different account types
- **Access**: Direct Core Data entity mapping

### Core Data Mapping
```
Account Types Discovered:
- BankChequeAccount (8) → checking
- BankSavingAccount (7) → savings  
- CashAccount (4) → cash
- CreditCardAccount (24) → credit_card
- LoanAccount (2) → loan
- InvestmentAccount (4) → investment
- ForexAccount (3) → forex
```

## 📁 Project Structure

```
moneywiz-mcp-server/
├── src/moneywiz_mcp_server/     # Main package
│   ├── server.py                # MCP server (working)
│   ├── config.py                # Configuration (working)
│   ├── database/connection.py   # Core Data access (working)
│   ├── tools/accounts.py        # Account tools (working)
│   └── utils/                   # Validation & formatting
├── specs/                       # Documentation
│   ├── implementation-status.md # Current status & next steps
│   └── *.md                     # Requirements & guides
├── tests/                       # Test suite
├── SETUP.md                     # Installation guide
├── test_mcp_connection.py       # Comprehensive test
└── continue-development.py      # Development continuation
```

## 🎯 Next Development Priorities

### 1. Transaction Tools (High Priority)
The foundation is ready. Next step is implementing transaction search and analytics:

```bash
# Research transaction entities (entities 37, 45, 46, 47)
python -c "
import asyncio
from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.config import Config

async def research():
    config = Config.from_env()
    db = DatabaseManager(config.database_path)
    await db.initialize()
    
    # Sample transaction data
    for entity_id in [37, 45, 46, 47]:
        txns = await db.execute_query('SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? LIMIT 1', (entity_id,))
        if txns:
            print(f'Entity {entity_id}: {list(txns[0].keys())[:10]}')
    
    await db.close()

asyncio.run(research())
"
```

### 2. Available Entity Data
Already discovered in the database:
- **Transactions**: 13,092 transaction records across 4 entity types
- **Categories**: 157 categories for spending analysis
- **Payees**: 512 payees for merchant analysis

## 🔒 Security & Safety

- **Read-only mode**: Database opened in read-only mode by default
- **Input validation**: All parameters validated before processing
- **Error handling**: Graceful fallbacks and error recovery
- **Privacy**: Local-only access, no external network calls

## 📖 Documentation

- **[SETUP.md](SETUP.md)** - Complete installation and configuration guide
- **[specs/implementation-status.md](specs/implementation-status.md)** - Detailed status and continuation guide
- **[specs/moneywiz-mcp-prd.md](specs/moneywiz-mcp-prd.md)** - Original requirements
- **[test_mcp_connection.py](test_mcp_connection.py)** - Comprehensive test script

## 🆘 Support

### Common Issues
1. **"No accounts found"** - Check MONEYWIZ_DB_PATH environment variable
2. **"Database not found"** - Verify MoneyWiz Setapp is installed and has data
3. **"Claude doesn't see MCP"** - Restart Claude Desktop after config changes

### Debugging
```bash
# Test database connection
python test_mcp_connection.py

# Check environment
echo $MONEYWIZ_DB_PATH

# Verify Claude Desktop config
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

## 🎉 Success!

Your MoneyWiz MCP server is **production-ready** for account operations and provides a **solid foundation** for extending with transaction and analytics features.

**Just restart Claude Desktop and start asking about your accounts!** 🏦💰