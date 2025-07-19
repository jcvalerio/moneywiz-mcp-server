# MoneyWiz MCP Server - Setup Guide

This guide walks you through setting up the MoneyWiz MCP server and connecting it to Claude Desktop.

## 📋 Prerequisites

1. **MoneyWiz App**: Install and set up MoneyWiz with some financial data
2. **Python 3.10+**: Ensure Python is installed
3. **Claude Desktop**: Install Claude Desktop application

## 🔍 Step 1: Locate Your MoneyWiz Database

First, you need to find where MoneyWiz stores its SQLite database.

### macOS Locations
```bash
# MoneyWiz 3 (most common)
~/Library/Containers/com.moneywiz.mac/Data/Documents/
~/Library/Containers/com.moneywiz.personalfinance/Data/Documents/

# Alternative locations
~/Library/Application Support/MoneyWiz/
~/Documents/MoneyWiz/
```

### Windows Locations
```cmd
# Common locations
%USERPROFILE%\AppData\Local\SilverWiz\MoneyWiz
%USERPROFILE%\AppData\Roaming\SilverWiz\MoneyWiz
%USERPROFILE%\Documents\MoneyWiz
```

### Find Your Database
```bash
# Search for MoneyWiz database files
find ~ -name "*.sqlite*" 2>/dev/null | grep -i moneywiz

# Or search more broadly
find ~ -name "*.sqlite*" -exec ls -la {} \; 2>/dev/null | grep -v system
```

Look for files named like:
- `MoneyWiz.sqlite`
- `database.sqlite`
- `moneywiz_data.sqlite`
- Any `.sqlite` file in MoneyWiz directories

## 🛠️ Step 2: Install the MCP Server

### Option A: Install from Source (Recommended for Testing)
```bash
# Clone the repository
git clone <repository-url>
cd moneywiz-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dependencies
pip install -e ".[dev,test]"

# Verify installation
python -m moneywiz_mcp_server --help
```

### Option B: Install from PyPI (When Available)
```bash
pip install moneywiz-mcp-server
```

## ⚙️ Step 3: Configure the Server

### Method 1: Environment Variables
```bash
# Set the database path
export MONEYWIZ_DB_PATH="/path/to/your/MoneyWiz.sqlite"

# Optional: Enable read-only mode (recommended for safety)
export MONEYWIZ_READ_ONLY=true
```

### Method 2: Configuration File
```bash
# Copy the example configuration
cp .env.example .env

# Edit .env file with your settings
nano .env
```

Example `.env` file:
```bash
MONEYWIZ_DB_PATH=/Users/username/Library/Containers/com.moneywiz.mac/Data/Documents/MoneyWiz.sqlite
MONEYWIZ_READ_ONLY=true
LOG_LEVEL=INFO
```

## 🧪 Step 4: Test the Server

### Test Database Connection
```bash
# Test if server can find and connect to database
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

### Test MCP Tools
```bash
# Test account listing (this will run as MCP tool test)
python -c "
from moneywiz_mcp_server.config import Config
from moneywiz_mcp_server.tools.accounts import list_accounts_tool
from moneywiz_mcp_server.database.connection import DatabaseManager
import asyncio

async def test():
    config = Config.from_env()
    db = DatabaseManager(config.database_path)
    await db.initialize()
    
    tool = list_accounts_tool(db)
    accounts = await tool.handler()
    print(f'✅ Found {len(accounts)} accounts')
    for acc in accounts[:3]:  # Show first 3
        print(f'  - {acc[\"name\"]}: {acc[\"balance\"]}')
    
    await db.close()

asyncio.run(test())
"
```

## 🖥️ Step 5: Configure Claude Desktop

### Find Claude Desktop Config
```bash
# macOS
~/Library/Application Support/Claude/claude_desktop_config.json

# Windows
%APPDATA%\Claude\claude_desktop_config.json
```

### Add MCP Server Configuration

Edit your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "python",
      "args": ["-m", "moneywiz_mcp_server"],
      "env": {
        "MONEYWIZ_DB_PATH": "/full/path/to/your/MoneyWiz.sqlite",
        "MONEYWIZ_READ_ONLY": "true"
      }
    }
  }
}
```

**Important Notes:**
- Use **full absolute paths** for the database file
- Ensure the path has no spaces or special characters, or quote properly
- Set `MONEYWIZ_READ_ONLY` to `true` for safety

### Alternative: Using Virtual Environment
If you installed in a virtual environment:

```json
{
  "mcpServers": {
    "moneywiz": {
      "command": "/full/path/to/venv/bin/python",
      "args": ["-m", "moneywiz_mcp_server"],
      "env": {
        "MONEYWIZ_DB_PATH": "/full/path/to/your/MoneyWiz.sqlite",
        "MONEYWIZ_READ_ONLY": "true"
      }
    }
  }
}
```

## 🚀 Step 6: Start Claude Desktop

1. **Restart Claude Desktop** completely (quit and reopen)
2. **Check Connection**: Look for MCP server indicators in Claude Desktop
3. **Test Integration**: Try asking Claude about your accounts

## 🧪 Step 7: Test with Claude

Try these example prompts in Claude Desktop:

### Basic Account Listing
```
Can you show me all my MoneyWiz accounts?
```

### Account Details
```
Can you give me details about my checking account?
```

### Account Filtering
```
Show me only my savings accounts from MoneyWiz
```

## 🐛 Troubleshooting

### Server Won't Start
```bash
# Check if database file exists and is readable
ls -la "/path/to/your/MoneyWiz.sqlite"

# Test database path resolution
python -c "from moneywiz_mcp_server.config import Config; print(Config.from_env().database_path)"

# Check server logs
python -m moneywiz_mcp_server 2>&1 | head -20
```

### Claude Desktop Connection Issues

1. **Check Configuration Syntax**:
   ```bash
   # Validate JSON syntax
   python -c "import json; print(json.load(open('claude_desktop_config.json')))"
   ```

2. **Check Logs**:
   - Look at Claude Desktop logs/console
   - Check for error messages during startup

3. **Verify Paths**:
   ```bash
   # Test the exact command Claude will run
   /full/path/to/python -m moneywiz_mcp_server
   ```

### Database Permission Issues
```bash
# Check file permissions
ls -la "/path/to/your/MoneyWiz.sqlite"

# Make readable (if needed)
chmod 644 "/path/to/your/MoneyWiz.sqlite"
```

### Common Issues

1. **"Database not found"**: 
   - Double-check the `MONEYWIZ_DB_PATH`
   - Use absolute paths only
   - Ensure MoneyWiz has created the database

2. **"Permission denied"**:
   - Check file permissions on database
   - Ensure MoneyWiz isn't exclusively locking the file

3. **"MCP server not responding"**:
   - Restart Claude Desktop
   - Check server logs for errors
   - Verify JSON configuration syntax

## 🔒 Security Notes

- **Read-Only Mode**: Always use read-only mode unless you specifically need write access
- **Local Access**: The server only accesses local database files
- **No Network**: No external network connections are made
- **Database Backup**: Consider backing up your MoneyWiz database before first use

## 📚 Next Steps

Once connected successfully:

1. **Explore Account Tools**: Try different account queries
2. **Set Up Monitoring**: Check server logs periodically  
3. **Read-Only Verification**: Confirm no unwanted changes to your data
4. **Advanced Usage**: Explore transaction searching (when implemented)

## 🆘 Getting Help

If you encounter issues:

1. **Check Logs**: Both server and Claude Desktop logs
2. **Verify Database**: Ensure MoneyWiz database is accessible
3. **Test Components**: Test database connection and MCP tools separately
4. **Configuration**: Double-check all paths and environment variables

---

**⚠️ Safety First**: Always start with read-only mode and verify everything works before considering write access.