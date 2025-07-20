# MoneyWiz MCP Server

A Model Context Protocol (MCP) server that provides AI assistants like Claude with secure, read-only access to your MoneyWiz financial data for natural language queries and financial analytics.

![Status: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-green)
![Platform: macOS](https://img.shields.io/badge/Platform-macOS-blue)
![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)

## 🚀 Quick Start (30 seconds)

```bash
# 1. Install the server
pip install git+https://github.com/jcvalerio/moneywiz-mcp-server.git

# 2. Set up configuration
python setup_env.py

# 3. Add to Claude Desktop config (~/.../Claude/claude_desktop_config.json)
{
  "mcpServers": {
    "moneywiz": {
      "command": "python",
      "args": ["-m", "moneywiz_mcp_server"]
    }
  }
}

# 4. Restart Claude Desktop and ask: "Show me my MoneyWiz accounts"
```

## ✨ What You Can Do

Ask Claude natural language questions about your finances:

### 💰 Account & Transaction Management
- **"Show me all my MoneyWiz accounts with their balances"**
- **"Get details for my checking account including recent transactions"**
- **"Search my transactions from last month in the Groceries category"**

### 📊 Expense Analytics
- **"Analyze my expenses for the last 3 months by category"**
- **"What's my savings rate this year?"**
- **"Which spending category impacts my finances the most?"**

### 💡 Advanced Analytics (New!)
- **"Give me personalized savings recommendations with 25% target rate"**
- **"Analyze my spending trends over the last 6 months"**
- **"Show me category trends for my top 5 spending categories"**
- **"Track my income vs expense trends for financial health"**

## 📋 Prerequisites

- **macOS**: MoneyWiz MCP Server only supports macOS (MoneyWiz is only available on Apple platforms)
- **MoneyWiz App**: Install and set up MoneyWiz with some financial data
- **Python 3.10+**: Ensure Python is installed
- **Claude Desktop**: Install Claude Desktop application

## 🛠️ Installation

### Option 1: Install from Source (Recommended)

```bash
# Clone the repository
git clone https://github.com/jcvalerio/moneywiz-mcp-server.git
cd moneywiz-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install with dependencies
pip install -e ".[dev,test]"

# Run setup to find your MoneyWiz database
python setup_env.py
```

### Option 2: Install from PyPI (When Available)

```bash
pip install moneywiz-mcp-server
```

## ⚙️ Configuration

### Automatic Setup (Recommended)

```bash
# Run the setup script to automatically find and configure your MoneyWiz database
python setup_env.py
```

The setup script will:
- Search for MoneyWiz databases on your Mac
- Let you select the correct database
- Create a `.env` file with your configuration
- Provide next steps for testing

### Manual Configuration

Create a `.env` file in the project root:

```bash
# MoneyWiz Database Path
MONEYWIZ_DB_PATH=/Users/yourusername/Library/Containers/com.moneywiz.personalfinance-setapp/Data/Documents/.AppData/ipadMoneyWiz.sqlite

# Security Settings  
MONEYWIZ_READ_ONLY=true

# Optional Settings
LOG_LEVEL=INFO
CACHE_TTL=300
MAX_RESULTS=1000
```

### Finding Your MoneyWiz Database

MoneyWiz stores data in these locations on macOS:

```bash
# MoneyWiz 3 (most common)
~/Library/Containers/com.moneywiz.mac/Data/Documents/
~/Library/Containers/com.moneywiz.personalfinance/Data/Documents/
~/Library/Containers/com.moneywiz.personalfinance-setapp/Data/Documents/

# MoneyWiz 2
~/Library/Application Support/SilverWiz/MoneyWiz 2/
```

Search command:
```bash
find ~ -name "*.sqlite*" 2>/dev/null | grep -i moneywiz
```

## 🖥️ Claude Desktop Setup

### 1. Find Your Claude Desktop Config

The configuration file is located at:
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

### 2. Add MCP Server Configuration

Choose one of these configurations:

#### Standard Installation
```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "python",
      "args": ["-m", "moneywiz_mcp_server"]
    }
  }
}
```

#### Virtual Environment (FastMCP Best Practice)
```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "/path/to/your/venv/bin/python",
      "args": ["-m", "moneywiz_mcp_server.main"],
      "cwd": "/path/to/your/moneywiz-mcp-server"
    }
  }
}
```

#### With Custom Database Path (FastMCP Best Practice)
```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "python",
      "args": ["-m", "moneywiz_mcp_server.main"],
      "cwd": "/path/to/your/moneywiz-mcp-server",
      "env": {
        "MONEYWIZ_DB_PATH": "/path/to/your/MoneyWiz.sqlite",
        "MONEYWIZ_READ_ONLY": "true"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

Completely quit and reopen Claude Desktop for changes to take effect.

## 🧪 Testing

### Test Database Connection
```bash
python -c "
from moneywiz_mcp_server.config import Config
from moneywiz_mcp_server.database.connection import DatabaseManager
import asyncio

async def test():
    config = Config.from_env()
    print(f'Database: {config.database_path}')
    db = DatabaseManager(config.database_path)
    await db.initialize()
    print('✅ Database connection successful!')
    await db.close()

asyncio.run(test())
"
```

### Test MCP Server
```bash
# Start the server (should connect via stdio)
python -m moneywiz_mcp_server
```

### Test with Claude Desktop

Try these queries in Claude Desktop:
- "Show me all my MoneyWiz accounts"
- "Analyze my expenses for the last 3 months"
- "What's my current savings rate?"

## 🛡️ Available Tools

Once configured, Claude will have access to these MoneyWiz tools:

### Account Management
- **`list_accounts`** - List all accounts with balances and types
- **`get_account`** - Get detailed account information by ID

### Financial Analytics  
- **`search_transactions`** - Search transactions with natural language time periods
- **`analyze_expenses_by_category`** - Analyze spending patterns by category
- **`analyze_income_vs_expenses`** - Compare income vs expenses with savings analysis

### Advanced Analytics (Phase 3)
- **`get_savings_recommendations`** - Personalized savings optimization with actionable tips
- **`analyze_spending_trends`** - Statistical trend analysis with projections and insights
- **`analyze_category_trends`** - Multi-category trend comparison and growth analysis
- **`analyze_income_expense_trends`** - Income vs expense sustainability tracking

## 🔧 Technical Details

### Architecture
- **MCP Server**: Modern FastMCP with decorator-based tool registration
- **Database**: Direct Core Data SQLite access (read-only by default)
- **Analytics**: Advanced savings optimization and trend analysis services
- **Safety**: Read-only mode by default with comprehensive input validation
- **Integration**: Seamless Claude Desktop integration with structured JSON responses

### Database Support
- **MoneyWiz 3**: Full support for latest version including Setapp
- **MoneyWiz 2**: Legacy support
- **Data**: Accounts, transactions, categories, payees
- **Size**: Efficiently handles databases with thousands of transactions

## 🐛 Troubleshooting

### Server Won't Start

```bash
# Check if database file exists
ls -la "/path/to/your/MoneyWiz.sqlite"

# Test configuration
python -c "from moneywiz_mcp_server.config import Config; print(Config.from_env().database_path)"

# Check server logs
python -m moneywiz_mcp_server 2>&1 | head -20
```

### Claude Desktop Connection Issues

1. **Validate JSON syntax**:
   ```bash
   python -c "import json; print(json.load(open('claude_desktop_config.json')))"
   ```

2. **Test exact command**:
   ```bash
   python -m moneywiz_mcp_server
   ```

3. **Check file permissions**:
   ```bash
   ls -la "/path/to/your/MoneyWiz.sqlite"
   ```

### Common Issues

- **"Database not found"**: Check `MONEYWIZ_DB_PATH` and use absolute paths
- **"Permission denied"**: Ensure file permissions and MoneyWiz isn't locking the file
- **"MCP server not responding"**: Restart Claude Desktop and check JSON syntax
- **"No data found"**: Ensure MoneyWiz has transaction data and is the correct database

## 🔒 Security

- **Read-Only Mode**: Database opened in read-only mode by default
- **Local Access**: Only accesses local database files
- **No Network**: No external network connections
- **Privacy**: All data processing happens locally
- **Validation**: All inputs validated before database queries

## 📁 Project Structure

```
moneywiz-mcp-server/
├── README.md                    # This file
├── pyproject.toml              # Package configuration
├── setup_env.py               # Setup helper script
├── examples/                   # Configuration examples
│   ├── claude_desktop_config.json
│   ├── claude_desktop_config_venv.json
│   └── claude_code_config.json
├── src/moneywiz_mcp_server/    # Main package
│   ├── server.py               # MCP server
│   ├── config.py               # Configuration
│   ├── database/               # Database connection
│   ├── tools/                  # MCP tools
│   ├── services/               # Business logic
│   └── utils/                  # Utilities
└── tests/                      # Test suite
```

## 🚀 Development

### Setup Development Environment
```bash
git clone https://github.com/jcvalerio/moneywiz-mcp-server.git
cd moneywiz-mcp-server
python -m venv venv
source venv/bin/activate
pip install -e ".[dev,test]"
python setup_env.py
```

### Run Tests
```bash
python -m pytest tests/ -v
```

### Code Quality
```bash
# Linting
flake8 src/
mypy src/

# Formatting
black src/
isort src/
```

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/jcvalerio/moneywiz-mcp-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/jcvalerio/moneywiz-mcp-server/discussions)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

**⚠️ Important**: Always use read-only mode and back up your MoneyWiz database before first use.