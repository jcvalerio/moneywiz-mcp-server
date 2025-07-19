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

- **"Show me all my MoneyWiz accounts with their balances"**
- **"Analyze my expenses for the last 3 months by category"**
- **"What's my savings rate this year?"**
- **"Which spending category impacts my finances the most?"**
- **"Search my transactions from last month in the Groceries category"**

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

#### Virtual Environment
```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "/path/to/your/venv/bin/python",
      "args": ["-m", "moneywiz_mcp_server"]
    }
  }
}
```

#### With Custom Database Path
```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "python",
      "args": ["-m", "moneywiz_mcp_server"],
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

## 🔧 Technical Details

### Architecture
- **MCP Server**: Modern decorator-based tool registration
- **Database**: Direct Core Data SQLite access (read-only by default)
- **Safety**: Read-only mode by default
- **Integration**: Seamless Claude Desktop integration

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