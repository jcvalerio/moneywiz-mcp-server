# Session Context for MoneyWiz MCP Server

## 🎯 Project Overview
MoneyWiz MCP server providing financial analytics for Claude Desktop integration. Enables natural language queries like "check my expenses for the last 3 months and identify which category is impacting more my finances".

## 🔧 Current Status (July 2024)

### ✅ Major Achievements
1. **Fixed Critical Balance Issue**: All accounts showing $0.00 → now showing correct values (e.g., $1,657.60)
2. **Implemented Financial Analytics**: Working expense analysis, income vs expense comparison
3. **Environment Configuration**: Professional .env setup, no hardcoded paths
4. **Claude Desktop Integration**: Working MCP server connection
5. **Category Resolution**: JUST FIXED - was showing all transactions as "Uncategorized"

### 🐛 Recently Fixed Critical Bug
**Problem**: All $24M+ in expenses showing as "Uncategorized" instead of actual category names
**Root Cause**: Incorrect category lookup - categories stored in separate `ZCATEGORYASSIGMENT` table
**Solution**: Fixed in `transaction_service.py:270-333` using correct table and `ZNAME2` field
**Status**: Fix implemented, needs testing via Claude Desktop

## 📁 Key Files to Know

### Core Implementation
- `src/moneywiz_mcp_server/services/transaction_service.py` - **MOST IMPORTANT** - just fixed category resolution
- `src/moneywiz_mcp_server/tools/analytics.py` - MCP tools for Claude Desktop
- `src/moneywiz_mcp_server/models/transaction.py` - Data models
- `launcher.py` - MCP server entry point

### Configuration
- `.env` - Database path and settings (user-specific, not in git)
- `.env.example` - Template for setup
- `setup_env.py` - Automatic MoneyWiz database detection
- `~/Library/Application Support/Claude/claude_desktop_config.json` - Claude Desktop MCP config

### Documentation
- `specs/financial-analytics-design.md` - **UPDATED** - Complete project specs with current status
- `SETUP.md` - User setup instructions
- `README.md` - Project overview

## 🗄️ Database Schema (Critical Knowledge)

### Account Balance Calculation (FIXED)
```sql
-- Get opening balance
SELECT ZOPENINGBALANCE FROM ZSYNCOBJECT WHERE Z_PK = ? AND Z_ENT BETWEEN 10 AND 16

-- Get transaction amounts (linked via ZACCOUNT2)
SELECT ZAMOUNT1 FROM ZSYNCOBJECT WHERE Z_ENT IN (37,45,46,47) AND ZACCOUNT2 = ?

-- Formula: opening_balance + sum(transaction_amounts)
```

### Category Resolution (JUST FIXED)
```sql
-- Step 1: Get category ID from assignment table (note missing 'N' in table name)
SELECT ca.ZCATEGORY FROM ZCATEGORYASSIGMENT ca WHERE ca.ZTRANSACTION = ?

-- Step 2: Get category name (use ZNAME2, not ZNAME)
SELECT ZNAME2 FROM ZSYNCOBJECT WHERE Z_ENT = 19 AND Z_PK = ?
```

### Transaction Entities
- 37: DepositTransaction (income)
- 45: TransferDepositTransaction (transfer in)
- 46: TransferWithdrawTransaction (transfer out)  
- 47: WithdrawTransaction (expenses)
- 38, 40, 41: Investment transactions
- 42, 43, 44: Reconcile, refund, budget transfers

## 🧪 Testing Status

### Working Features
- ✅ Account listing with correct balances
- ✅ Transaction search and filtering
- ✅ Expense analysis by date range
- ✅ Income vs expense comparison
- ✅ Claude Desktop MCP integration

### Recently Fixed
- ✅ Category resolution (was completely broken)

### Needs Testing
- 🔄 Verify category fix shows proper category names instead of "Uncategorized"

## 🚀 Immediate Next Steps

1. **Test Category Fix**: Run expense analysis via Claude Desktop to verify categories work
2. **Complete Phase 2**: Implement savings optimization recommendations  
3. **Expand Tests**: Create comprehensive test suite

## 🔧 Development Commands

```bash
# Start MCP server for testing
python launcher.py

# Run tests
python -m pytest tests/ -v

# Check environment
python setup_env.py

# Git status (on feature/financial-analytics branch)
git status
```

## 💡 Key Technical Insights

### MoneyWiz Database Structure
- Core Data SQLite database with entities numbered by type
- Account balances calculated from opening balance + transaction sums
- Categories linked via separate assignment table (common pattern)
- Multiple currency support built-in

### MCP Server Architecture
- Tool-based architecture with decorators
- Service layer for business logic
- Models for data structures
- Environment-based configuration

### Critical Fixes Applied
1. **Balance Calculation**: Changed from wrong fields to correct MoneyWiz formula
2. **Category Resolution**: Fixed table name and field name for category lookup
3. **Environment Config**: Removed hardcoded personal paths

## 🎯 Project Goals

**Primary**: Enable natural language financial queries through Claude Desktop
**Secondary**: Provide savings optimization recommendations
**Tertiary**: Support advanced financial analytics and trends

## 🔒 Security Notes
- Read-only database access
- No sensitive data in logs
- Personal information anonymized in git commits
- Environment variables for configuration

This context should provide sufficient information for any future Claude Code session to understand the project state and continue development effectively.