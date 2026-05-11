# MoneyWiz MCP Server

A Model Context Protocol (MCP) server that provides AI assistants like Claude with secure, read-only access to your MoneyWiz financial data for natural language queries and financial analytics.

![Status: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-green)
![Platform: macOS](https://img.shields.io/badge/Platform-macOS-blue)
![Python: 3.12](https://img.shields.io/badge/Python-3.12-blue)

## 🚀 Quick Start

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone https://github.com/jcvalerio/moneywiz-mcp-server.git
cd moneywiz-mcp-server
uv sync --all-extras

# 3. Find your MoneyWiz database
uv run python setup_env.py

# 4. Add to Claude Desktop config and restart
```

See [Claude Desktop Setup](#️-claude-desktop-setup) below for the exact JSON configuration.

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

### 💡 Advanced Analytics
- **"Give me personalized savings recommendations with 25% target rate"**
- **"Analyze my spending trends over the last 6 months"**
- **"Show me category trends for my top 5 spending categories"**
- **"Track my income vs expense trends for financial health"**

### 📅 Scheduled Transactions & Recurring Payments
- **"Show me all my scheduled transactions"**
- **"What recurring payments do I have coming up?"**
- **"Analyze how my next salary covers my commitments"**
- **"When will my subscriptions and loans end?"**

### 💵 Budget Management
- **"Show me all my budgets with spending status"**
- **"Am I on track with my monthly budgets?"**
- **"Compare my budgeted amounts vs actual spending"**
- **"Which budgets are at risk of going over?"**

## 📋 Prerequisites

- **macOS**: MoneyWiz MCP Server only supports macOS (MoneyWiz is only available on Apple platforms)
- **MoneyWiz App**: Install and set up MoneyWiz with some financial data
- **uv**: Install the uv package manager — it manages Python automatically, no separate Python install required
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Claude Desktop**: Install Claude Desktop application

> **No system Python required.** uv downloads and manages Python 3.12 automatically when you run `uv sync`.

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/jcvalerio/moneywiz-mcp-server.git
cd moneywiz-mcp-server

# Install all dependencies (creates .venv with Python 3.12 automatically)
uv sync --all-extras

# Run setup to find your MoneyWiz database
uv run python setup_env.py
```

## 📌 Stable Releases and Rollback

For day-to-day use, prefer a tagged stable release once one is published. This keeps your Claude Desktop setup on known-good behavior while new roadmap work continues.

```bash
# From an existing source checkout
git fetch --tags
git checkout v1.0.0
uv sync --all-extras
uv run python setup_env.py
```

To upgrade intentionally, read the release notes first, then check out the desired version:

```bash
git fetch --tags
git checkout vX.Y.Z
uv sync --all-extras
```

To roll back, return to the previous known-good tag and restart Claude Desktop:

```bash
git fetch --tags
git checkout vPREVIOUS_VERSION
uv sync --all-extras
```

The Claude Desktop configuration below remains compatible with pinned source checkouts as long as the checkout directory does not move. See [Releasing](docs/RELEASING.md) for the versioning policy and maintainer checklist.

## ⚙️ Configuration

### Automatic Setup (Recommended)

```bash
uv run python setup_env.py
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

```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

### 2. Add MCP Server Configuration

Claude Desktop does not source your shell, so bare commands like `python` or `uv` won't be found. Use absolute paths in the configuration.

#### Option A: Source Checkout

Use this option if you cloned the repository and ran `uv sync --all-extras`.

```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "/ABSOLUTE/PATH/TO/moneywiz-mcp-server/.venv/bin/python",
      "args": ["-m", "moneywiz_mcp_server"],
      "cwd": "/ABSOLUTE/PATH/TO/moneywiz-mcp-server"
    }
  }
}
```

**Get your absolute path:**
```bash
echo "$(pwd)/.venv/bin/python"
# Example output: /Users/yourname/dev/moneywiz-mcp-server/.venv/bin/python
```

The `.venv/bin/python` binary is self-contained — it does **not** require Python to be installed globally on your Mac.

The `cwd` field is required so the server can locate the `.env` file with your database path.

#### Option B: PyPI with `uvx`

Use this option if you want Claude Desktop to run the published package without a source checkout. Because there is no checkout-local `.env` file in this mode, provide the MoneyWiz database path through the `env` block.

First, find the absolute path to `uv`:

```bash
command -v uv
# Example output: /Users/yourname/.local/bin/uv
```

Then configure Claude Desktop. Pin the package version for stable behavior, and replace `MONEYWIZ_DB_PATH` with your actual SQLite database path.

```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "/ABSOLUTE/PATH/TO/uv",
      "args": [
        "x",
        "--from",
        "moneywiz-mcp-server==1.0.1",
        "moneywiz-mcp-server"
      ],
      "env": {
        "MONEYWIZ_DB_PATH": "/ABSOLUTE/PATH/TO/ipadMoneyWiz.sqlite",
        "MONEYWIZ_READ_ONLY": "true"
      }
    }
  }
}
```

If you prefer to use the newest published package instead of a pinned version, remove `==1.0.1`. Pinned versions are recommended for day-to-day use.

### 3. Restart Claude Desktop

Completely quit and reopen Claude Desktop for changes to take effect.

## 🧪 Testing

### Test Database Connection
```bash
uv run python -c "
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
uv run python -m moneywiz_mcp_server
```

## 🛡️ Available Tools

Once configured, Claude will have access to these MoneyWiz tools:

### Account Management
- **`list_accounts`** - List all accounts with balances and types
- **`get_account`** - Get detailed account information by ID

### Transaction Management
- **`search_transactions`** - Search transactions with natural language time periods and filters

### Financial Analytics
- **`analyze_expenses_by_category`** - Analyze spending patterns by category
- **`analyze_income_vs_expenses`** - Compare income vs expenses with savings analysis

### Advanced Analytics
- **`get_savings_recommendations`** - Personalized savings optimization with actionable tips
- **`analyze_spending_trends`** - Statistical trend analysis with projections and insights
- **`analyze_category_trends`** - Multi-category trend comparison and growth analysis
- **`analyze_income_expense_trends`** - Income vs expense sustainability tracking

### Scheduled Transactions & Recurring Payments
- **`get_scheduled_transactions`** - List all scheduled and recurring transactions
- **`analyze_salary_breakdown`** - Analyze how salary covers commitments
- **`get_commitments_ending_timeline`** - Track when subscriptions, loans, and recurring payments end

### Budget Management
- **`get_budgets`** - List all budgets with spending status and percentages
- **`analyze_budget_performance`** - Analyze which budgets are on track or at risk
- **`get_budget_vs_actual`** - Compare budgeted amounts vs actual spending by category

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
uv run python -c "from moneywiz_mcp_server.config import Config; print(Config.from_env().database_path)"

# Check server logs
uv run python -m moneywiz_mcp_server 2>&1 | head -20
```

### Claude Desktop Connection Issues

1. **Validate JSON syntax**:
   ```bash
   python3 -c "import json; print(json.load(open('$HOME/Library/Application Support/Claude/claude_desktop_config.json')))"
   ```

2. **Verify the .venv Python path exists**:
   ```bash
   ls -la /ABSOLUTE/PATH/TO/moneywiz-mcp-server/.venv/bin/python
   ```

3. **Test the exact command Claude Desktop will run**:
   ```bash
   /ABSOLUTE/PATH/TO/moneywiz-mcp-server/.venv/bin/python -m moneywiz_mcp_server
   ```

4. **Check file permissions**:
   ```bash
   ls -la "/path/to/your/MoneyWiz.sqlite"
   ```

### Common Issues

- **"Database not found"**: Check `MONEYWIZ_DB_PATH` in `.env` and use absolute paths
- **"Permission denied"**: Ensure file permissions and MoneyWiz isn't locking the file
- **"MCP server not responding"**: Restart Claude Desktop and verify the `.venv/bin/python` path is correct
- **"No data found"**: Ensure MoneyWiz has transaction data and is the correct database
- **"command not found"**: Make sure you're using the absolute `.venv/bin/python` path, not bare `python`

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
├── uv.lock                     # Locked dependency versions
├── .python-version             # Python version pin (3.12.7)
├── setup_env.py               # Setup helper script
├── examples/                   # Configuration examples
│   ├── claude_desktop_config.json
│   ├── claude_desktop_config_venv.json
│   └── claude_code_config.json
├── src/moneywiz_mcp_server/    # Main package
│   ├── main.py                 # FastMCP server entry point
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
uv sync --all-extras
uv run python setup_env.py
```

### Run Tests
```bash
uv run pytest tests/ -v
```

### Code Quality
```bash
uv run ruff check .        # Linting
uv run ruff format .       # Formatting
uv run mypy src/           # Type checking
./scripts/check-ci.sh     # Full CI simulation
```

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/jcvalerio/moneywiz-mcp-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/jcvalerio/moneywiz-mcp-server/discussions)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

**⚠️ Important**: Always use read-only mode and back up your MoneyWiz database before first use.
