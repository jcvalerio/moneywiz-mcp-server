"""Account-related MCP tools for MoneyWiz server."""

from datetime import datetime
import logging
from typing import Any

from mcp.types import Tool

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.utils.formatters import format_currency
from moneywiz_mcp_server.utils.validators import (
    validate_account_id,
    validate_account_type,
)

logger = logging.getLogger(__name__)


async def calculate_account_balance(
    db_manager: DatabaseManager, account_pk: int
) -> float:
    """Calculate the real account balance using MoneyWiz's formula.

    Based on moneywiz-api source code analysis:
    balance = opening_balance + sum(all_transaction_amounts)

    Args:
        db_manager: Database manager instance
        account_pk: Account's Z_PK value

    Returns:
        Real account balance calculated using MoneyWiz formula
    """
    try:
        # Get account opening balance (ZOPENINGBALANCE, not ZBALLANCE)
        account_query = """
        SELECT ZOPENINGBALANCE
        FROM ZSYNCOBJECT
        WHERE Z_PK = ? AND Z_ENT BETWEEN 10 AND 16
        """

        account_result = await db_manager.execute_query(account_query, (account_pk,))
        if not account_result:
            logger.warning(f"Account {account_pk} not found")
            return 0.0

        opening_balance = float(account_result[0].get("ZOPENINGBALANCE", 0))

        # Get all transactions for this account using correct fields:
        # - Use ZAMOUNT1 (not ZORIGINALAMOUNT)
        # - Link via ZACCOUNT2 (as per DepositTransaction in moneywiz-api)
        # - Include entities 37,45,46,47 but exclude TransferBudgetTransaction
        transactions_query = """
        SELECT ZAMOUNT1
        FROM ZSYNCOBJECT
        WHERE Z_ENT IN (37, 45, 46, 47)
        AND ZACCOUNT2 = ?
        """

        transactions = await db_manager.execute_query(transactions_query, (account_pk,))

        # Sum transaction amounts (using ZAMOUNT1)
        transaction_total = sum(
            float(txn.get("ZAMOUNT1", 0) or 0) for txn in transactions
        )

        # MoneyWiz formula: opening_balance + sum(transaction_amounts)
        final_balance = opening_balance + transaction_total

        logger.debug(
            f"Account {account_pk}: opening={opening_balance}, transactions={transaction_total}, final={final_balance}"
        )
        return final_balance

    except Exception as e:
        logger.warning(f"Failed to calculate balance for account {account_pk}: {e}")
        return 0.0


def list_accounts_tool(db_manager: DatabaseManager) -> Tool:
    """Create the list_accounts MCP tool.

    Args:
        db_manager: Database manager instance

    Returns:
        Configured MCP Tool for listing accounts
    """

    async def handler(
        include_hidden: bool = False, account_type: str | None = None
    ) -> list[dict[str, Any]]:
        """List all accounts with balances and metadata.

        Args:
            include_hidden: Whether to include hidden accounts
            account_type: Filter accounts by type (optional)

        Returns:
            List of account dictionaries with formatted data

        Raises:
            ValueError: If account_type is invalid
            RuntimeError: If database operations fail
        """
        logger.info(
            f"Listing accounts (include_hidden={include_hidden}, type={account_type})"
        )

        # Validate account type filter if provided
        if account_type:
            validate_account_type(account_type)

        try:
            # Get all accounts from Core Data directly
            # Account entities: 10=BankCheque, 11=BankSaving, 12=Cash, 13=CreditCard, 14=Loan, 15=Investment, 16=Forex
            account_entities = [10, 11, 12, 13, 14, 15, 16]

            # Get entity type mapping
            entity_map = await db_manager.execute_query(
                "SELECT Z_ENT, Z_NAME FROM Z_PRIMARYKEY WHERE Z_ENT IN (10,11,12,13,14,15,16)"
            )
            entity_types = {e["Z_ENT"]: e["Z_NAME"] for e in entity_map}

            all_accounts = []
            for entity_id in account_entities:
                query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ?"
                accounts = await db_manager.execute_query(query, (entity_id,))

                for account in accounts:
                    # Skip hidden accounts if not requested
                    if not include_hidden and account.get("ZARCHIVED", 0) == 1:
                        continue

                    # Map entity to account type
                    entity_name = entity_types.get(entity_id, "unknown")
                    account_type_mapping = {
                        "BankChequeAccount": "checking",
                        "BankSavingAccount": "savings",
                        "CashAccount": "cash",
                        "CreditCardAccount": "credit_card",
                        "LoanAccount": "loan",
                        "InvestmentAccount": "investment",
                        "ForexAccount": "forex",
                    }
                    mapped_type = account_type_mapping.get(entity_name, "unknown")

                    # Filter by type if specified
                    if account_type and mapped_type != account_type:
                        continue

                    all_accounts.append(
                        {
                            "account": account,
                            "entity_type": entity_name,
                            "mapped_type": mapped_type,
                        }
                    )

            logger.debug(f"Retrieved {len(all_accounts)} accounts from database")

            # Format accounts for response
            result = []
            for item in all_accounts:
                account = item["account"]

                # Calculate real balance from transactions
                account_pk = account.get("Z_PK", 0)
                real_balance = await calculate_account_balance(db_manager, account_pk)

                # Format account data for response
                formatted_account = {
                    "id": account.get("ZGID", str(account.get("Z_PK", ""))),
                    "name": account.get("ZNAME", "Unnamed Account"),
                    "type": item["mapped_type"],
                    "balance": format_currency(
                        real_balance, account.get("ZCURRENCYNAME", "USD")
                    ),
                    "currency": account.get("ZCURRENCYNAME", "USD"),
                    "entity_type": item["entity_type"],
                    "last_updated": datetime.now().isoformat(),
                    "archived": bool(account.get("ZARCHIVED", 0)),
                }

                result.append(formatted_account)

            logger.info(f"Returning {len(result)} accounts after filtering")
            return result

        except Exception as e:
            logger.error(f"Failed to list accounts: {e}")
            raise RuntimeError(f"Failed to retrieve accounts: {e!s}") from e

    return Tool(
        name="list_accounts",
        description="List all MoneyWiz accounts with current balances",
        inputSchema={
            "type": "object",
            "properties": {
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden accounts in results",
                    "default": False,
                },
                "account_type": {
                    "type": "string",
                    "description": "Filter accounts by type",
                    "enum": [
                        "checking",
                        "savings",
                        "credit_card",
                        "investment",
                        "cash",
                        "loan",
                        "property",
                    ],
                },
            },
        },
        handler=handler,
    )


def get_account_tool(db_manager: DatabaseManager) -> Tool:
    """Create the get_account MCP tool.

    Args:
        db_manager: Database manager instance

    Returns:
        Configured MCP Tool for getting account details
    """

    async def handler(
        account_id: str, include_transactions: bool = False
    ) -> dict[str, Any]:
        """Get detailed information about a specific account.

        Args:
            account_id: Unique identifier for the account
            include_transactions: Whether to include recent transactions

        Returns:
            Dictionary with account details and optional transactions

        Raises:
            ValueError: If account_id is invalid or account not found
            RuntimeError: If database operations fail
        """
        logger.info(
            f"Getting account details for {account_id} (include_txns={include_transactions})"
        )

        # Validate account ID
        validate_account_id(account_id)

        try:
            # Get account details from Core Data directly
            # Search by ZGID or Z_PK
            account_entities = [10, 11, 12, 13, 14, 15, 16]

            # Get entity type mapping
            entity_map = await db_manager.execute_query(
                "SELECT Z_ENT, Z_NAME FROM Z_PRIMARYKEY WHERE Z_ENT IN (10,11,12,13,14,15,16)"
            )
            entity_types = {e["Z_ENT"]: e["Z_NAME"] for e in entity_map}

            account = None
            entity_name = None

            # Search for account by ID across all account entities
            for entity_id in account_entities:
                query = """SELECT * FROM ZSYNCOBJECT
                          WHERE Z_ENT = ? AND (ZGID = ? OR Z_PK = ?)"""
                try:
                    # Try both ZGID and Z_PK matching
                    pk_value = int(account_id) if account_id.isdigit() else 0
                    results = await db_manager.execute_query(
                        query, (entity_id, account_id, pk_value)
                    )
                    if results:
                        account = results[0]
                        entity_name = entity_types.get(entity_id, "unknown")
                        break
                except ValueError:
                    # If account_id is not a number, skip Z_PK matching
                    query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ? AND ZGID = ?"
                    results = await db_manager.execute_query(
                        query, (entity_id, account_id)
                    )
                    if results:
                        account = results[0]
                        entity_name = entity_types.get(entity_id, "unknown")
                        break

            if not account:
                raise ValueError(f"Account {account_id} not found")

            logger.debug(f"Retrieved account: {account.get('ZNAME', 'Unnamed')}")

            # Map entity to account type
            account_type_mapping = {
                "BankChequeAccount": "checking",
                "BankSavingAccount": "savings",
                "CashAccount": "cash",
                "CreditCardAccount": "credit_card",
                "LoanAccount": "loan",
                "InvestmentAccount": "investment",
                "ForexAccount": "forex",
            }
            mapped_type = account_type_mapping.get(entity_name, "unknown")

            # Calculate real balance from transactions
            account_pk = account.get("Z_PK", 0)
            real_balance = await calculate_account_balance(db_manager, account_pk)

            # Format account details
            result = {
                "id": account.get("ZGID", str(account.get("Z_PK", ""))),
                "name": account.get("ZNAME", "Unnamed Account"),
                "type": mapped_type,
                "balance": format_currency(
                    real_balance, account.get("ZCURRENCYNAME", "USD")
                ),
                "currency": account.get("ZCURRENCYNAME", "USD"),
                "entity_type": entity_name,
                "archived": bool(account.get("ZARCHIVED", 0)),
                "created_date": account.get("ZOBJECTCREATIONDATE", ""),
                "institution": account.get("ZBANKWEBSITEURL", ""),
                "account_info": account.get("ZINFO", ""),
                "last_four_digits": account.get("ZLASTFOURDIGITS", ""),
            }

            # Optionally include recent transactions
            if include_transactions:
                logger.debug("Including recent transactions")
                try:
                    # For now, add placeholder - transactions would require understanding
                    # the transaction entity structure which is more complex
                    result["recent_transactions"] = []
                    result[
                        "transactions_note"
                    ] = "Transaction history integration coming soon"

                except Exception as e:
                    logger.warning(
                        f"Failed to get transactions for account {account_id}: {e}"
                    )
                    # Don't fail the whole request, just omit transactions
                    result["recent_transactions"] = []

            return result

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(f"Failed to get account {account_id}: {e}")
            raise RuntimeError(f"Failed to retrieve account details: {e!s}") from e

    return Tool(
        name="get_account",
        description="Get detailed information about a specific account",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "The unique account identifier",
                },
                "include_transactions": {
                    "type": "boolean",
                    "description": "Include recent transactions in response",
                    "default": False,
                },
            },
            "required": ["account_id"],
        },
        handler=handler,
    )
