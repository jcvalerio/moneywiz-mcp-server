# Financial Analytics Architecture Design

## 🎯 **Feature Overview**

Design and implement advanced financial analytics capabilities for the MoneyWiz MCP server, enabling natural language queries for expense analysis, category insights, and savings optimization.

## 🔄 **Current Implementation Status (July 2024)**

### ✅ **Completed Components**
This project has made significant progress with the following components implemented and working:

#### **Phase 1: Foundation - COMPLETED**
- ✅ **Fixed Balance Calculation**: Resolved critical issue where all account balances showed $0.00
  - Used moneywiz-api source code analysis to identify correct formula: `ZOPENINGBALANCE + sum(ZAMOUNT1)`
  - Fixed account linking using `ZACCOUNT2` field instead of incorrect approaches
  - Validated against actual MoneyWiz desktop app showing $1,657.60 vs previous -$230,240.66 errors

- ✅ **Transaction Service Layer**: Complete implementation with category resolution
  - `src/moneywiz_mcp_server/services/transaction_service.py` - Full transaction querying, filtering, and enhancement
  - **Critical Fix**: Category resolution using `ZCATEGORYASSIGMENT` table (note missing 'N') and `ZNAME2` field
  - Caching for categories, payees, and account currencies
  - Support for all transaction types (37, 45, 46, 47, 38, 40, 41, 42, 43, 44)

- ✅ **Data Models**: Complete transaction and analytics models
  - `src/moneywiz_mcp_server/models/transaction.py` - TransactionModel with full Core Data mapping
  - `src/moneywiz_mcp_server/models/analytics_result.py` - IncomeExpenseAnalysis, CategoryExpense models
  - Support for all MoneyWiz transaction types and currency handling

- ✅ **MCP Tools Implementation**: Working analytics tools
  - `src/moneywiz_mcp_server/tools/analytics.py` - analyze_expenses, analyze_income_vs_expenses tools
  - `src/moneywiz_mcp_server/tools/transactions.py` - search_transactions tool
  - Integration with existing accounts.py tools

#### **Infrastructure & Environment**
- ✅ **Git Repository**: Initialized with proper configuration
  - 1Password SSH signing configured
  - Personal information anonymized in commits
  - Feature branch: `feature/financial-analytics` created

- ✅ **Environment Configuration**: Production-ready setup
  - `.env` system implemented to remove hardcoded paths
  - `setup_env.py` script for automatic MoneyWiz database detection
  - `launcher.py` updated to use environment variables
  - Claude Desktop integration configured in `claude_desktop_config.json`

- ✅ **Testing Framework**: Basic test structure
  - `tests/` directory with unit and integration test framework
  - Sample tests for analytics functionality
  - Coverage tracking setup

#### **Database Integration**
- ✅ **MoneyWiz Database Analysis**: Complete understanding
  - Transaction entities: 37 (deposit), 45/46 (transfers), 47 (withdraw), 38/40/41 (investments)
  - Category system: Entity 19 with ZCATEGORYASSIGMENT table linking
  - Account entities: 10-16 with proper currency and balance fields
  - Verified against `/Users/jcvalerio/jcvalerio/dev/github/moneywiz-api` source code

### 🔄 **Recently Fixed Critical Issues**

#### **Category Resolution Fix (Latest)**
**Problem**: All transactions were showing as "Uncategorized" instead of actual category names, making expense analysis useless (all $24M+ expenses showed as "Uncategorized")

**Root Cause Analysis**: 
- Categories are NOT stored directly in transaction records
- MoneyWiz uses separate `ZCATEGORYASSIGMENT` table (note missing 'N' in spelling)
- Category names are in `ZNAME2` field, not `ZNAME`
- Previous implementation was looking for categories in wrong table/field

**Solution Implemented** (`transaction_service.py:270-333`):
```python
# Fixed query in _enhance_transaction method
category_assignment_query = """
SELECT ca.ZCATEGORY
FROM ZCATEGORYASSIGMENT ca  -- Note: missing 'N' is correct
WHERE ca.ZTRANSACTION = ?
LIMIT 1
"""

# Fixed category name lookup using ZNAME2
category_query = "SELECT ZNAME2 FROM ZSYNCOBJECT WHERE Z_ENT = 19 AND Z_PK = ?"
```

**Status**: Fix implemented, ready for testing with Claude Desktop

### 🚧 **Current Development Status**

#### **Phase 2: Core Analytics - IN PROGRESS**
- ✅ **Expense Analysis**: `get_expense_summary()` method implemented with category breakdown
- ✅ **Income vs Expense**: `get_income_vs_expense()` method with savings rate calculation
- ✅ **Transaction Filtering**: Date range, account, category, and transaction type filtering
- 🔄 **Category Resolution**: Just fixed, needs validation through Claude Desktop testing

#### **Next Immediate Tasks**
1. **Test Category Fix**: Verify expense analysis now shows proper categories via Claude Desktop
2. **Phase 2 Completion**: Implement remaining savings optimization recommendations
3. **Comprehensive Testing**: Expand test suite for all analytics functionality

### 📁 **Key File Locations for Continuation**

## 📋 **Requirements Analysis**

### **Core User Stories**
1. **Expense Tracking**: "Check my expenses for the last 3 months"
2. **Category Analysis**: "Which category is impacting my finances the most?"
3. **Income vs Expense**: "Check my income and expenses"
4. **Savings Optimization**: "How can I increase my savings?"

### **Technical Requirements**
- Natural language query processing
- Time-based transaction filtering (last N months/days)
- Category-based expense aggregation
- Income vs expense flow analysis
- Trend analysis and recommendations
- Multi-currency support
- Performance optimization for large datasets

## 🏗️ **System Architecture**

**Core Implementation Files**:
- `src/moneywiz_mcp_server/services/transaction_service.py` - Main transaction logic (JUST FIXED category resolution)
- `src/moneywiz_mcp_server/tools/analytics.py` - MCP analytics tools
- `src/moneywiz_mcp_server/tools/transactions.py` - Transaction search tools
- `src/moneywiz_mcp_server/models/transaction.py` - Transaction data models
- `src/moneywiz_mcp_server/models/analytics_result.py` - Analytics result models
- `launcher.py` - MCP server launcher with environment config
- `.env` - Environment configuration (user-specific, not in git)
- `.env.example` - Template for environment setup

**Database Connection**:
- `src/moneywiz_mcp_server/database/connection.py` - Database manager
- MoneyWiz database: `$MONEYWIZ_DB_PATH` (configured in .env)
- Read-only access for safety

**Configuration**:
- Claude Desktop config: `~/.config/claude-desktop/config.json` or `~/Library/Application Support/Claude/claude_desktop_config.json`
- MCP server configured as "moneywiz" with launcher.py

### **Component Implementation Status**
```
MoneyWiz MCP Server
├── tools/
│   ├── accounts.py (✅ WORKING - balance calculation fixed)
│   ├── transactions.py (✅ IMPLEMENTED - search_transactions tool)
│   ├── analytics.py (✅ IMPLEMENTED - analyze_expenses, income_vs_expenses tools)
│   └── insights.py (❌ NOT STARTED - savings recommendations)
├── services/
│   ├── transaction_service.py (✅ IMPLEMENTED - JUST FIXED category resolution)
│   ├── analytics_service.py (❌ NOT NEEDED - logic in transaction_service)
│   └── recommendation_service.py (❌ NOT STARTED - for Phase 2)
├── models/
│   ├── transaction.py (✅ IMPLEMENTED - complete TransactionModel)
│   ├── category.py (❌ NOT NEEDED - using direct queries)
│   └── analytics_result.py (✅ IMPLEMENTED - IncomeExpenseAnalysis, CategoryExpense)
└── utils/
    ├── date_utils.py (✅ IMPLEMENTED - Core Data timestamp conversion)
    ├── currency_utils.py (❌ NOT STARTED - future enhancement)
    └── formatters.py (✅ EXISTING - inherited from original)
```

### **Database Entities (MoneyWiz Core Data)**
Based on analysis and moneywiz-api source code verification:

**Core Entities**:
- **Transactions**: Entities 37 (deposit), 45 (transfer-in), 46 (transfer-out), 47 (withdraw)
- **Investment Transactions**: Entities 38 (exchange), 40 (buy), 41 (sell), 42 (reconcile), 43 (refund), 44 (budget)
- **Categories**: Entity 19 - **CRITICAL**: Linked via `ZCATEGORYASSIGMENT` table, names in `ZNAME2` field
- **Payees**: Entity 28 - Names in `ZNAME` field
- **Accounts**: Entities 10-16 - Balance calculation: `ZOPENINGBALANCE + sum(ZAMOUNT1)` linked via `ZACCOUNT2`

**Database Schema Critical Details**:
```sql
-- Transaction to Category Linking (FIXED)
SELECT ca.ZCATEGORY FROM ZCATEGORYASSIGMENT ca WHERE ca.ZTRANSACTION = ?

-- Category Names (FIXED - use ZNAME2, not ZNAME)
SELECT ZNAME2 FROM ZSYNCOBJECT WHERE Z_ENT = 19 AND Z_PK = ?

-- Account Balance Calculation (FIXED)
SELECT ZOPENINGBALANCE FROM ZSYNCOBJECT WHERE Z_PK = ? AND Z_ENT BETWEEN 10 AND 16
SELECT ZAMOUNT1 FROM ZSYNCOBJECT WHERE Z_ENT IN (37,45,46,47) AND ZACCOUNT2 = ?
-- Formula: opening_balance + sum(transaction_amounts)

-- Transaction Fields
-- ZAMOUNT1: Account-level amount (used for balance calculation)
-- ZACCOUNT2: Links transaction to account
-- ZDATE1: Transaction date (Core Data timestamp)
-- ZDESC2: Transaction description
-- ZPAYEE2: Payee ID reference
```

## 📊 **Data Flow Architecture**

### **Query Processing Pipeline**
1. **MCP Tool Receives Query** → Natural language input
2. **Parameter Extraction** → Parse time periods, categories, amounts
3. **Database Query Construction** → Build efficient SQL queries
4. **Data Aggregation** → Process and summarize results
5. **Analysis Engine** → Apply analytical algorithms
6. **Recommendation Engine** → Generate actionable insights
7. **Response Formatting** → Return structured data to Claude

### **Performance Considerations**
- **Indexed Queries**: Optimize for date range and category filtering
- **Caching Strategy**: Cache category mappings and frequent aggregations
- **Batch Processing**: Handle large transaction volumes efficiently
- **Memory Management**: Stream large result sets

## 🔧 **Implementation Design**

### **1. Transaction Service Layer**

```python
class TransactionService:
    async def get_transactions(
        self,
        start_date: datetime,
        end_date: datetime,
        account_ids: List[int] = None,
        categories: List[str] = None,
        transaction_types: List[str] = None
    ) -> List[TransactionModel]
    
    async def get_expense_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: str = "category"
    ) -> ExpenseSummary
    
    async def get_income_vs_expense(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> IncomeExpenseAnalysis
```

### **2. Analytics Service Layer**

```python
class AnalyticsService:
    async def analyze_spending_by_category(
        self,
        months: int = 3
    ) -> CategoryAnalysisResult
    
    async def identify_top_expense_categories(
        self,
        months: int = 3,
        limit: int = 5
    ) -> List[CategoryImpact]
    
    async def analyze_savings_potential(
        self,
        months: int = 3
    ) -> SavingsAnalysis
    
    async def get_spending_trends(
        self,
        months: int = 6
    ) -> TrendAnalysis
```

### **3. MCP Tools Design**

```python
# tools/analytics.py
def analyze_expenses_tool(db_manager: DatabaseManager) -> Tool:
    """Analyze expenses for specified time period"""
    
def category_impact_tool(db_manager: DatabaseManager) -> Tool:
    """Identify categories with highest financial impact"""
    
def income_expense_analysis_tool(db_manager: DatabaseManager) -> Tool:
    """Compare income vs expenses and identify savings opportunities"""
    
def savings_recommendations_tool(db_manager: DatabaseManager) -> Tool:
    """Generate personalized savings recommendations"""
```

## 🧪 **Test-Driven Development Plan**

### **Test Coverage Requirements**
- **Unit Tests**: ≥90% coverage for all service layers
- **Integration Tests**: ≥85% coverage for MCP tool interactions
- **Performance Tests**: Query response time <2s for 10K transactions
- **Edge Case Tests**: Empty datasets, single transactions, multi-currency

### **Test Structure**
```
tests/
├── unit/
│   ├── test_transaction_service.py
│   ├── test_analytics_service.py
│   └── test_recommendation_service.py
├── integration/
│   ├── test_analytics_tools.py
│   └── test_end_to_end_queries.py
└── fixtures/
    ├── sample_transactions.py
    └── expected_analytics_results.py
```

## 🔍 **Data Models**

### **Transaction Model**
```python
@dataclass
class TransactionModel:
    id: str
    account_id: int
    amount: Decimal
    date: datetime
    category: str
    payee: Optional[str]
    description: str
    transaction_type: TransactionType
    currency: str
```

### **Analytics Results**
```python
@dataclass
class CategoryAnalysisResult:
    total_expenses: Decimal
    category_breakdown: List[CategoryExpense]
    top_categories: List[CategoryImpact]
    analysis_period: DateRange
    currency: str

@dataclass
class SavingsAnalysis:
    current_savings_rate: float
    potential_savings: Decimal
    recommendations: List[SavingsRecommendation]
    spending_patterns: SpendingPatterns
```

## 🚀 **Implementation Phases**

### **Phase 1: Foundation - ✅ COMPLETED**
1. ✅ Create transaction service layer - `transaction_service.py` implemented
2. ✅ Implement basic transaction querying - `get_transactions()` method working
3. ✅ Set up test framework for analytics - Basic test structure in place
4. ✅ Design category mapping system - **JUST FIXED** category resolution via ZCATEGORYASSIGMENT

### **Phase 2: Core Analytics - 🔄 90% COMPLETE**
1. ✅ Implement expense analysis by category - `get_expense_summary()` implemented
2. ✅ Create income vs expense analysis - `get_income_vs_expense()` implemented
3. ✅ Build time-based filtering - Date range filtering working
4. ✅ Add multi-currency support - Basic support implemented
5. 🔄 **NEXT**: Test category resolution fix with Claude Desktop
6. ❌ **PENDING**: Implement savings optimization recommendations

### **Phase 3: Advanced Features - ❌ NOT STARTED**
1. ❌ Implement savings recommendations - Create `recommendation_service.py`
2. ❌ Add trend analysis - Monthly/quarterly trend analysis
3. ❌ Create performance optimizations - Query optimization, better caching
4. ❌ Build comprehensive test suite - Expand beyond basic tests

### **Phase 4: Integration & Polish - 🔄 PARTIALLY COMPLETE**
1. ✅ Integrate with existing MCP server - Working with Claude Desktop
2. ✅ Add comprehensive error handling - Basic error handling implemented
3. ✅ Create user documentation - SETUP.md updated
4. ❌ Performance tuning and optimization - Not started

## 📈 **Success Metrics**

### **Functional Requirements Status**
- ✅ Handle "last 3 months" time-based queries - Working
- 🔄 Identify top spending categories accurately - **JUST FIXED**, needs testing
- ❌ Provide actionable savings recommendations - Phase 3 pending
- ✅ Support multi-currency transactions - Basic support implemented
- ✅ Maintain existing account balance accuracy - Fixed and verified

### **Known Issues FIXED**
- ✅ **Balance Calculation**: Fixed $0.00 balance issue, now shows correct values like $1,657.60
- ✅ **Category Resolution**: Fixed "Uncategorized" issue by using ZCATEGORYASSIGMENT table and ZNAME2 field
- ✅ **Environment Configuration**: Removed hardcoded paths, uses .env system
- ✅ **Claude Desktop Integration**: MCP server working with proper configuration

### **Performance Requirements**
- Query response time: <2 seconds for 6 months of data
- Memory usage: <100MB for typical datasets
- Test coverage: >90% for critical paths
- Error rate: <0.1% for valid queries

## 🔐 **Security & Safety**

### **Data Privacy**
- Read-only database access (no modifications)
- No sensitive financial data in logs
- Secure parameter validation
- Input sanitization for all queries

### **Error Handling**
- Graceful fallback for invalid date ranges
- Proper handling of empty result sets
- Clear error messages for users
- Comprehensive logging for debugging

## 📚 **Documentation Plan**

### **Technical Documentation**
- API documentation for all new tools
- Service layer architecture guide
- Database query optimization guide
- Testing strategy and best practices

### **User Documentation**
- Example queries and expected responses
- Troubleshooting guide
- Performance considerations
- Integration guide for Claude Desktop

## 🔄 **Continuation Guide for Future Sessions**

### **Immediate Next Steps**
1. **Test Category Resolution Fix**: 
   - Run MCP server: `python launcher.py`
   - Test via Claude Desktop expense analysis
   - Verify categories show actual names instead of "Uncategorized"
   - Previous test showed all $24M+ as "Uncategorized", should now show proper breakdown

2. **Complete Phase 2**:
   - Implement savings optimization recommendations in `tools/insights.py`
   - Create `recommendation_service.py` for savings analysis
   - Add trend analysis capabilities

3. **Expand Testing**:
   - Create comprehensive test suite in `tests/`
   - Add performance tests for large datasets
   - Validate multi-currency support

### **Key Commands for Development**
```bash
# Start MCP server
python launcher.py

# Run tests
python -m pytest tests/ -v

# Check environment setup
python setup_env.py

# Git workflow
git checkout feature/financial-analytics
git add .
git commit -m "Category resolution fix"
```

### **Critical Context for Future Sessions**

**Balance Calculation Formula**: `ZOPENINGBALANCE + sum(ZAMOUNT1)` where transactions link via `ZACCOUNT2`

**Category Resolution**: Use `ZCATEGORYASSIGMENT` table → get `ZCATEGORY` → lookup `ZNAME2` in entity 19

**Database Location**: Configured in `.env` file as `MONEYWIZ_DB_PATH`

**MCP Configuration**: Claude Desktop configured to use `launcher.py` in moneywiz-mcp-server

**Recent Fix**: Category resolution was completely broken (all "Uncategorized"), just implemented fix using correct table structure based on moneywiz-api analysis

### **File Priority for Continuation**
1. `src/moneywiz_mcp_server/services/transaction_service.py` - Core logic, recently fixed
2. `src/moneywiz_mcp_server/tools/analytics.py` - MCP tools interface
3. `tests/` - Expand test coverage
4. `specs/` - Update with implementation progress

This implementation has solid foundations with working transaction analysis, account balance calculation, and environment configuration. The major recent fix addressed category resolution which was preventing proper expense analysis. Ready for testing and Phase 2 completion.