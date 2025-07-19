# MoneyWiz MCP Server - Claude Code Instructions

## 🎯 Project Overview

MoneyWiz MCP (Model Context Protocol) server providing financial analytics capabilities for Claude Desktop integration. Enables natural language queries for expense analysis, category insights, and savings optimization.

## 📋 Current Project Status

### ✅ Working Components
- **Account Balance Calculation**: Fixed from $0.00 to correct values (e.g., $1,657.60)
- **Financial Analytics Tools**: Working expense analysis and income vs expense comparison
- **Claude Desktop Integration**: MCP server properly configured and working
- **Environment Configuration**: Professional .env setup with no hardcoded paths
- **Category Resolution**: **RECENTLY FIXED** - categories now resolve properly instead of "Uncategorized"

### 🔧 Recent Critical Fix
**Category Resolution Issue**: All transactions were showing as "Uncategorized" instead of actual category names. Fixed by using correct MoneyWiz database structure:
- Categories stored in separate `ZCATEGORYASSIGMENT` table (note missing 'N')
- Category names in `ZNAME2` field, not `ZNAME`
- Fix implemented in `src/moneywiz_mcp_server/services/transaction_service.py:270-333`

## 🗂️ Key Project Files

### Core Implementation (Priority Order)
1. **`src/moneywiz_mcp_server/services/transaction_service.py`** - Main business logic, recently fixed
2. **`src/moneywiz_mcp_server/tools/analytics.py`** - MCP tools for Claude Desktop
3. **`src/moneywiz_mcp_server/tools/transactions.py`** - Transaction search tools
4. **`src/moneywiz_mcp_server/models/transaction.py`** - Data models
5. **`launcher.py`** - MCP server entry point

### Configuration & Setup
- **`.env`** - Environment configuration (user-specific, not in git)
- **`.env.example`** - Template for environment setup
- **`setup_env.py`** - Automatic MoneyWiz database detection script
- **Claude Desktop Config**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Documentation
- **`specs/financial-analytics-design.md`** - Complete project specifications and current status
- **`SESSION_CONTEXT.md`** - Detailed project context for continuation
- **`SETUP.md`** - User setup instructions

## 🗄️ MoneyWiz Database Knowledge

### Critical Database Schema
```sql
-- Account Balance (FIXED FORMULA)
-- Formula: ZOPENINGBALANCE + sum(ZAMOUNT1) where ZACCOUNT2 links transactions to accounts
SELECT ZOPENINGBALANCE FROM ZSYNCOBJECT WHERE Z_PK = ? AND Z_ENT BETWEEN 10 AND 16;
SELECT ZAMOUNT1 FROM ZSYNCOBJECT WHERE Z_ENT IN (37,45,46,47) AND ZACCOUNT2 = ?;

-- Category Resolution (RECENTLY FIXED)
-- Step 1: Get category ID from assignment table
SELECT ca.ZCATEGORY FROM ZCATEGORYASSIGMENT ca WHERE ca.ZTRANSACTION = ?;
-- Step 2: Get category name using ZNAME2 field
SELECT ZNAME2 FROM ZSYNCOBJECT WHERE Z_ENT = 19 AND Z_PK = ?;
```

### Entity Types
- **Accounts**: Entities 10-16
- **Transactions**: 37 (deposit), 45 (transfer-in), 46 (transfer-out), 47 (withdraw)
- **Investments**: 38 (exchange), 40 (buy), 41 (sell), 42 (reconcile), 43 (refund), 44 (budget)
- **Categories**: Entity 19 (linked via ZCATEGORYASSIGMENT table)
- **Payees**: Entity 28

## 🚀 Development Commands

```bash
# Start MCP server for testing
python launcher.py

# Run tests
python -m pytest tests/ -v

# Check/setup environment
python setup_env.py

# Git workflow (on feature/financial-analytics branch)
git status
git add .
git commit -m "Description"
```

## 🎯 Current Development Priorities

### Immediate Next Steps
1. **Test Category Resolution Fix**: Verify expense analysis shows proper categories via Claude Desktop
2. **Complete Phase 2**: Implement savings optimization recommendations
3. **Expand Test Suite**: Add comprehensive tests for all analytics features

### Implementation Phases
- **Phase 1** ✅: Foundation (transaction service, models, basic analytics)
- **Phase 2** 🔄: Core Analytics (90% complete - need savings optimization)
- **Phase 3** ❌: Advanced Features (savings recommendations, trend analysis)
- **Phase 4** 🔄: Integration & Polish (partially complete)

## 🧪 Testing & Validation

### Working Features
- Account listing with correct balances
- Transaction search and filtering by date/category/amount
- Expense analysis by category with percentage breakdown
- Income vs expense comparison with savings rate
- Claude Desktop MCP integration

### Recently Fixed
- Category resolution (was showing all as "Uncategorized")
- Balance calculation (was showing $0.00 for all accounts)

### Test Commands
```bash
# Test MCP server connection
python launcher.py

# Run specific test suites
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
```

## 🔒 Security & Best Practices

### Database Access
- **Read-only access**: Database opened in read-only mode for safety
- **No data modification**: Server only reads financial data, never writes
- **Input validation**: All parameters validated before database queries

### Configuration
- **Environment variables**: All paths and settings in .env file
- **No hardcoded paths**: Personal information externalized
- **Git safety**: .env files excluded from git commits

## 💡 Technical Architecture

### MCP Server Structure
```
MoneyWiz MCP Server
├── tools/ (MCP tool implementations)
├── services/ (Business logic layer)
├── models/ (Data structures)
├── database/ (Database connection management)
└── utils/ (Helper functions)
```

### Data Flow
1. Claude Desktop → MCP Tool Request
2. Tool → Service Layer (business logic)
3. Service → Database Manager (SQL queries)
4. Database → MoneyWiz SQLite (read-only)
5. Response → Tool → Claude Desktop

## 🔧 Known Issues & Solutions

### Fixed Issues
- **Balance Calculation**: Used wrong fields/formula → Fixed with MoneyWiz-api analysis
- **Category Resolution**: Wrong table/field lookup → Fixed with ZCATEGORYASSIGMENT/ZNAME2
- **Environment Config**: Hardcoded paths → Fixed with .env system
- **Claude Desktop Integration**: Connection issues → Fixed with proper launcher

### Current Limitations
- Basic savings recommendations (Phase 3 pending)
- Limited trend analysis capabilities
- No advanced performance optimizations

## 📚 Additional Context

### Project History
- Started with basic account listing (working)
- Fixed critical balance calculation issue (all accounts showed $0.00)
- Implemented financial analytics framework
- Recently fixed category resolution (all transactions showed "Uncategorized")
- Git repository initialized with proper 1Password SSH signing

### MoneyWiz Integration
- Based on analysis of moneywiz-api source code: `/Users/jcvalerio/jcvalerio/dev/github/moneywiz-api`
- Understands MoneyWiz Core Data structure and relationships
- Maintains compatibility with MoneyWiz desktop application data

## 🎯 Success Criteria

### Functional Goals
- ✅ Natural language expense queries ("expenses for last 3 months")
- 🔄 Category impact analysis ("which category impacts finances most")
- ✅ Income vs expense comparison
- ❌ Savings optimization recommendations (Phase 2 pending)

### Technical Goals
- ✅ Claude Desktop integration working
- ✅ Read-only database access
- ✅ Environment-based configuration
- ✅ Error handling and validation
- 🔄 Comprehensive test coverage (basic structure in place)

This project is in excellent shape with working core functionality and recent critical fixes. Ready for testing the category resolution fix and completing Phase 2 savings optimization features.