# MoneyWiz MCP Server - Architecture

## Overview

MoneyWiz MCP Server is a Model Context Protocol (MCP) server that provides secure, read-only access to MoneyWiz personal finance data. It enables AI assistants like Claude to perform natural language financial analysis and insights.

## System Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Claude Desktop /   │     │   MCP Server     │     │ MoneyWiz SQLite │
│  Other MCP Clients  │◄────┤  (Python)        ├────►│    Database     │
└─────────────────────┘     └──────────────────┘     └─────────────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │  Direct SQLite   │
                            │     Access       │
                            └──────────────────┘
```

## Technology Stack

- **Language**: Python 3.10+
- **MCP Framework**: Official Python MCP SDK
- **Database**: Direct SQLite access to MoneyWiz Core Data
- **Async Support**: aiosqlite for non-blocking database operations
- **Data Validation**: Pydantic for input/output validation
- **Date Handling**: python-dateutil for natural language date parsing

## Core Components

### 1. Server Layer (`src/moneywiz_mcp_server/server.py`)

The main MCP server implementation using decorator-based tool registration:

```python
@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Register available MCP tools"""

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    """Handle tool execution requests"""
```

### 2. Database Layer (`src/moneywiz_mcp_server/database/`)

- **DatabaseManager**: Async SQLite connection management
- **Core Data Integration**: Direct access to MoneyWiz's Core Data SQLite structure
- **Read-Only Safety**: Database opened in read-only mode by default
- **Connection Pooling**: Efficient connection lifecycle management

### 3. Tools Layer (`src/moneywiz_mcp_server/tools/`)

MCP tool implementations organized by functionality:

- **accounts.py**: Account listing and balance retrieval
- **transactions.py**: Transaction search and filtering
- **analytics.py**: Financial analysis and insights

### 4. Models Layer (`src/moneywiz_mcp_server/models/`)

Data models for structured financial data:

- **TransactionModel**: Core transaction data structure
- **Analytics Results**: Structured analysis outputs
- **Date Handling**: Core Data timestamp conversion utilities

## MoneyWiz Database Schema

### Core Data Entities

MoneyWiz uses Core Data with the following key entity types:

#### Account Types (Entities 10-16)
- **10**: Bank Checking Account → 'checking'
- **11**: Bank Savings Account → 'savings'
- **12**: Cash Account → 'cash'
- **13**: Credit Card Account → 'credit_card'
- **14**: Loan Account → 'loan'
- **15**: Investment Account → 'investment'
- **16**: Forex Account → 'forex'

#### Transaction Types (Entities 37, 45-47)
- **37**: Deposit Transaction
- **45**: Transfer Deposit Transaction
- **46**: Transfer Withdraw Transaction
- **47**: Withdraw Transaction

#### Other Entities
- **19**: Categories
- **28**: Payees

### Key Database Operations

#### Account Balance Calculation
```sql
-- Get opening balance
SELECT ZOPENINGBALANCE FROM ZSYNCOBJECT
WHERE Z_PK = ? AND Z_ENT BETWEEN 10 AND 16;

-- Sum transaction amounts
SELECT SUM(ZAMOUNT1) FROM ZSYNCOBJECT
WHERE Z_ENT IN (37,45,46,47) AND ZACCOUNT2 = ?;

-- Formula: balance = opening_balance + sum(transaction_amounts)
```

#### Category Resolution
```sql
-- Get category assignment
SELECT ca.ZCATEGORY FROM ZCATEGORYASSIGMENT ca
WHERE ca.ZTRANSACTION = ?;

-- Get category name
SELECT ZNAME2 FROM ZSYNCOBJECT
WHERE Z_ENT = 19 AND Z_PK = ?;
```

## MCP Tools

### Account Tools
- **list_accounts**: Retrieve all accounts with balances and metadata
- **get_account**: Fetch specific account details

### Transaction Tools
- **search_transactions**: Query transactions with natural language filters
- **analyze_expenses_by_category**: Category-based expense analysis
- **analyze_income_vs_expenses**: Income vs expense comparison with savings rate

### Analytics Tools
- **Financial Insights**: Spending patterns and trends
- **Savings Analysis**: Optimization recommendations
- **Category Impact**: Identify high-impact spending categories

## Data Flow

### Query Processing Pipeline
1. **MCP Tool Receives Query** → Natural language input from Claude
2. **Parameter Extraction** → Parse time periods, categories, amounts
3. **Database Query Construction** → Build efficient SQL queries
4. **Data Aggregation** → Process and summarize results
5. **Analysis Engine** → Apply analytical algorithms
6. **Response Formatting** → Return structured data to Claude

### Natural Language Processing
- **Time Periods**: "last 3 months", "this year", "last 30 days"
- **Categories**: Expense category filtering and analysis
- **Amounts**: Range-based filtering and comparisons
- **Accounts**: Multi-account analysis and comparison

## Security & Safety

### Data Protection
- **Read-Only Access**: Database opened in read-only mode
- **No Data Modification**: Server only reads financial data
- **Input Validation**: All parameters validated before database queries
- **Error Sanitization**: Database errors don't expose internal structure

### Privacy Considerations
- **Local Access Only**: No external network communication
- **No Data Storage**: Server doesn't cache or store financial data
- **Audit Trail**: Comprehensive logging for debugging without sensitive data

## Performance Considerations

### Database Optimization
- **Indexed Queries**: Optimized for date range and category filtering
- **Async Operations**: Non-blocking database access
- **Connection Management**: Efficient connection pooling
- **Query Batching**: Minimize database round trips

### Memory Management
- **Streaming Results**: Handle large transaction volumes efficiently
- **Lazy Loading**: Load data on demand
- **Connection Cleanup**: Proper resource disposal

## Error Handling

### Graceful Degradation
- **Database Unavailable**: Clear error messages with troubleshooting guidance
- **Invalid Queries**: Helpful validation error messages
- **Data Inconsistency**: Fallback strategies for edge cases
- **Resource Limits**: Protection against memory/time exhaustion

### Logging Strategy
- **Structured Logging**: Machine-readable log formats
- **Debug Information**: Detailed logging for development
- **Error Context**: Sufficient context for troubleshooting
- **Privacy Protection**: No sensitive financial data in logs

## Development Guidelines

### Code Organization
- **Separation of Concerns**: Clear boundaries between layers
- **Type Safety**: Comprehensive type hints throughout
- **Error Propagation**: Consistent error handling patterns
- **Testing Strategy**: Unit and integration tests for all components

### Extension Points
- **New Tools**: Simple addition of new MCP tools
- **Analytics**: Extensible analysis framework
- **Data Sources**: Potential for additional financial data sources
- **Output Formats**: Flexible response formatting

This architecture provides a solid foundation for secure, efficient financial data access while maintaining the simplicity and reliability required for an MCP server.
