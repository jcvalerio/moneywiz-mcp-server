# MoneyWiz MCP Server - Product Requirements Document

## Executive Summary

This document outlines the requirements for developing a Model Context Protocol (MCP) server that enables AI assistants (particularly Claude) to interact with MoneyWiz personal finance data. The server will provide secure, local access to MoneyWiz SQLite database for financial analysis, expense tracking, and transaction management while leveraging MoneyWiz's native cloud sync capabilities.

## 1. Product Overview

### 1.1 Problem Statement
- MoneyWiz lacks a public API for third-party integrations
- Users need AI-powered financial insights and analysis
- Manual transaction entry for unsupported banks is time-consuming
- No programmatic way to perform bulk operations or advanced queries

### 1.2 Solution
Build an MCP server that:
- Directly interfaces with MoneyWiz's local SQLite database
- Exposes financial data and operations through standardized MCP tools
- Enables AI assistants to perform complex financial analysis
- Maintains data integrity while MoneyWiz handles cloud synchronization

### 1.3 Value Proposition
- **For Users**: AI-powered financial insights, automated transaction management, and intelligent spending analysis
- **For Developers**: Standardized integration with MoneyWiz without reverse-engineering
- **For AI Applications**: Rich financial context for better assistance

## 2. Technical Architecture

### 2.1 Architecture Decision

**Recommended Approach**: Python-based MCP server with local SQLite access

**Rationale**:
- Existing `moneywiz-api` Python library provides SQLite interface
- Python has mature MCP SDK support
- SQLite operations are well-supported in Python
- Easier to maintain and extend compared to TypeScript for database operations

### 2.2 System Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Claude Desktop /   │     │   MCP Server     │     │ MoneyWiz SQLite │
│  Other MCP Clients  │◄────┤  (Python)        ├────►│    Database     │
└─────────────────────┘     └──────────────────┘     └─────────────────┘
                                     │                         ▲
                                     ▼                         │
                            ┌──────────────────┐              │
                            │  moneywiz-api    │              │
                            │  Python Library  │──────────────┘
                            └──────────────────┘
```

### 2.3 Technology Stack
- **Language**: Python 3.10+
- **MCP SDK**: `mcp[cli]` (official Python SDK)
- **Database Access**: `moneywiz-api` library
- **Additional Libraries**:
  - `pandas` for data analysis
  - `python-dateutil` for date parsing
  - `pydantic` for data validation
  - `asyncio` for async operations

## 3. Feature Requirements

### 3.1 Core Features (MVP)

#### 3.1.1 Account Management
- **List All Accounts**: Retrieve all accounts with balances and metadata
- **Get Account Details**: Fetch specific account information
- **Account Balances**: Get current and historical balances
- **Account Types**: Support for checking, savings, credit cards, investments

#### 3.1.2 Transaction Operations
- **List Transactions**: Query transactions with filters (date range, amount, category)
- **Create Transaction**: Add new expenses, income, or transfers
- **Update Transaction**: Modify existing transactions
- **Delete Transaction**: Remove transactions
- **Bulk Import**: Import multiple transactions from CSV/JSON

#### 3.1.3 Category Management
- **List Categories**: Get all expense/income categories
- **Category Analysis**: Spending by category over time
- **Create/Update Categories**: Manage category hierarchy

#### 3.1.4 Financial Analysis
- **Spending Patterns**: Analyze spending trends by time period
- **Budget Analysis**: Compare actual vs budgeted amounts
- **Cash Flow**: Income vs expenses over time
- **Account Reconciliation**: Verify account balances

### 3.2 Extended Features (Phase 2)

#### 3.2.1 Investment Tracking
- **Portfolio Overview**: Current holdings and performance
- **Transaction History**: Buy/sell transactions
- **Performance Metrics**: ROI, gains/losses

#### 3.2.2 Advanced Analytics
- **Predictive Analysis**: Forecast future spending
- **Anomaly Detection**: Identify unusual transactions
- **Savings Recommendations**: AI-powered savings opportunities
- **Tax Preparation**: Category-based tax summaries

#### 3.2.3 Integration Features
- **Bank Statement Parser**: Extract transactions from PDFs
- **Receipt OCR**: Extract transaction data from receipts
- **URL Schema Integration**: Leverage MoneyWiz URL schemas

### 3.3 Non-Functional Requirements

#### 3.3.1 Security
- **Local-Only Access**: No network exposure of database
- **Read-Only Mode**: Optional safety mode
- **Session Management**: Secure session handling
- **Data Validation**: Strict input validation

#### 3.3.2 Performance
- **Response Time**: < 500ms for basic queries
- **Concurrent Access**: Handle multiple tool calls
- **Caching**: Smart caching for frequently accessed data
- **Batch Operations**: Efficient bulk transaction handling

#### 3.3.3 Reliability
- **Database Locking**: Proper SQLite locking mechanisms
- **Error Handling**: Graceful error recovery
- **Data Integrity**: No corruption of MoneyWiz database
- **Backup Support**: Optional backup before write operations

## 4. MCP Tool Specifications

### 4.1 Account Tools

```python
# List all accounts
tool: "list_accounts"
parameters: {
  "include_hidden": boolean (optional, default: false)
  "account_type": string (optional, filter by type)
}
returns: [{
  "id": string,
  "name": string,
  "type": string,
  "balance": number,
  "currency": string,
  "last_updated": datetime
}]

# Get account details
tool: "get_account"
parameters: {
  "account_id": string (required)
  "include_transactions": boolean (optional, default: false)
}
returns: {
  "id": string,
  "name": string,
  "type": string,
  "balance": number,
  "currency": string,
  "created_date": datetime,
  "transactions": array (if requested)
}
```

### 4.2 Transaction Tools

```python
# Search transactions
tool: "search_transactions"
parameters: {
  "account_id": string (optional),
  "start_date": date (optional),
  "end_date": date (optional),
  "min_amount": number (optional),
  "max_amount": number (optional),
  "category": string (optional),
  "payee": string (optional),
  "description": string (optional),
  "limit": number (optional, default: 100)
}
returns: [{
  "id": string,
  "date": date,
  "amount": number,
  "category": string,
  "payee": string,
  "description": string,
  "account": string,
  "type": string
}]

# Create transaction
tool: "create_transaction"
parameters: {
  "account_id": string (required),
  "amount": number (required),
  "date": date (required),
  "category": string (required),
  "payee": string (optional),
  "description": string (optional),
  "type": string (required: "expense", "income", "transfer")
}
returns: {
  "id": string,
  "success": boolean,
  "message": string
}
```

### 4.3 Analysis Tools

```python
# Get spending by category
tool: "analyze_spending_by_category"
parameters: {
  "start_date": date (required),
  "end_date": date (required),
  "account_ids": array[string] (optional)
}
returns: [{
  "category": string,
  "total_amount": number,
  "transaction_count": number,
  "percentage": number,
  "subcategories": array
}]

# Cash flow analysis
tool: "analyze_cash_flow"
parameters: {
  "period": string (required: "daily", "weekly", "monthly", "yearly"),
  "start_date": date (required),
  "end_date": date (required),
  "account_ids": array[string] (optional)
}
returns: [{
  "period": string,
  "income": number,
  "expenses": number,
  "net_flow": number,
  "running_balance": number
}]
```

## 5. Implementation Plan

### 5.1 Phase 1: MVP (Weeks 1-2)
1. **Week 1**: Core Infrastructure
   - Set up Python MCP server framework
   - Integrate moneywiz-api library
   - Implement basic account and transaction tools
   - Error handling and logging

2. **Week 2**: Essential Features
   - Transaction search and filtering
   - Basic financial analysis tools
   - Testing and documentation
   - Claude Desktop integration

### 5.2 Phase 2: Enhanced Features (Weeks 3-4)
3. **Week 3**: Advanced Operations
   - Bulk transaction import
   - Category management
   - Advanced analytics

4. **Week 4**: Polish and Optimization
   - Performance optimization
   - Caching layer
   - Comprehensive testing
   - User documentation

### 5.3 Phase 3: Extended Features (Month 2)
- Investment tracking
- Receipt OCR integration
- Predictive analytics
- URL schema integration

## 6. Security Considerations

### 6.1 Data Protection
- **Local-Only Operation**: No network exposure
- **Read-Only Default**: Write operations require explicit permission
- **Session Isolation**: Each MCP session is isolated
- **No Credential Storage**: No banking credentials stored

### 6.2 Database Safety
- **Backup Mechanism**: Optional automatic backup before writes
- **Transaction Rollback**: Support for operation rollback
- **Lock Management**: Proper SQLite locking
- **Validation**: Strict input validation to prevent injection

## 7. Testing Strategy

### 7.1 Unit Testing
- Test each tool independently
- Mock database operations
- Validate input/output schemas

### 7.2 Integration Testing
- Test with actual MoneyWiz database
- Verify data integrity after operations
- Test concurrent access scenarios

### 7.3 End-to-End Testing
- Test with Claude Desktop
- Verify conversation flows
- Test error scenarios

## 8. Documentation Requirements

### 8.1 User Documentation
- Installation guide
- Configuration instructions
- Tool usage examples
- Troubleshooting guide

### 8.2 Developer Documentation
- API reference
- Database schema documentation
- Extension guide
- Contributing guidelines

## 9. Success Metrics

### 9.1 Technical Metrics
- Response time < 500ms for 95% of queries
- Zero database corruption incidents
- 99.9% uptime during active sessions

### 9.2 User Metrics
- Successful transaction import rate > 95%
- Accurate financial analysis results
- Positive user feedback on AI interactions

## 10. Risks and Mitigation

### 10.1 Technical Risks
- **Database Corruption**: Implement robust backup and rollback
- **Version Compatibility**: Test with multiple MoneyWiz versions
- **Performance Issues**: Implement caching and query optimization

### 10.2 User Risks
- **Data Loss**: Always backup before write operations
- **Incorrect Analysis**: Validate calculations against MoneyWiz
- **Privacy Concerns**: Ensure local-only operation

## 11. Future Considerations

### 11.1 Potential Enhancements
- Multi-currency support improvements
- Machine learning for categorization
- Natural language transaction entry
- Voice-based interaction support

### 11.2 Ecosystem Integration
- Integration with other MCP servers
- Support for financial institution APIs
- Export to accounting software
- Tax preparation integrations

## Appendix A: MoneyWiz Database Schema

Based on the moneywiz-api library, the key tables include:
- Accounts
- Transactions
- Categories
- Payees
- Investment Holdings
- Scheduled Transactions

## Appendix B: MCP Protocol Compliance

The server will implement:
- Standard MCP lifecycle (initialize, shutdown)
- Tool discovery and invocation
- Error handling per MCP specification
- Session management
- Resource declarations (for account lists)

## Appendix C: Development Resources

- MCP Specification: https://modelcontextprotocol.io
- Python MCP SDK: https://github.com/modelcontextprotocol/python-sdk
- moneywiz-api: https://github.com/ileodo/moneywiz-api
- MoneyWiz URL Schemas: https://help.wiz.money/en/articles/4525440

---

This PRD serves as the comprehensive guide for implementing the MoneyWiz MCP server. It prioritizes safety, reliability, and user value while maintaining technical excellence and MCP compliance.