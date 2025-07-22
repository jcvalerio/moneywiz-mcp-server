"""Account service for MoneyWiz MCP Server."""

import logging
from typing import Any

from moneywiz_mcp_server.database.connection import DatabaseManager

logger = logging.getLogger(__name__)


class AccountService:
    """Service for account operations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def list_accounts(
        self, include_hidden: bool = False, account_type: str | None = None
    ) -> list[dict[str, Any]]:
        """List all accounts with balances."""
        # Account entities: 10=BankCheque, 11=BankSaving, 12=Cash, 13=CreditCard, 14=Loan, 15=Investment, 16=Forex
        account_entities = [10, 11, 12, 13, 14, 15, 16]

        # Get entity type mapping
        entity_map = await self.db_manager.execute_query(
            "SELECT Z_ENT, Z_NAME FROM Z_PRIMARYKEY WHERE Z_ENT IN (10,11,12,13,14,15,16)"
        )
        entity_types = {e["Z_ENT"]: e["Z_NAME"] for e in entity_map}

        accounts_data = []
        for entity_id in account_entities:
            query = "SELECT * FROM ZSYNCOBJECT WHERE Z_ENT = ?"
            accounts = await self.db_manager.execute_query(query, (entity_id,))

            for account in accounts:
                if not include_hidden and account.get("ZARCHIVED", 0) == 1:
                    continue

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

                if account_type and mapped_type != account_type:
                    continue

                # Calculate balance
                opening_balance = account.get("ZOPENINGBALANCE", 0)
                balance_query = "SELECT SUM(ZAMOUNT1) as total FROM ZSYNCOBJECT WHERE Z_ENT IN (37,45,46,47) AND ZACCOUNT2 = ?"
                balance_result = await self.db_manager.execute_query(
                    balance_query, (account["Z_PK"],)
                )
                transaction_total = (
                    balance_result[0]["total"]
                    if balance_result and balance_result[0]["total"]
                    else 0
                )
                current_balance = opening_balance + transaction_total

                accounts_data.append(
                    {
                        "id": account.get("ZGID", str(account["Z_PK"])),
                        "name": account.get("ZNAME", "Unknown Account"),
                        "type": mapped_type,
                        "balance": current_balance,
                        "currency": account.get("ZCURRENCYNAME", "USD"),
                        "hidden": bool(account.get("ZARCHIVED", 0)),
                        "institution": account.get("ZINSTITUTIONNAME", ""),
                        "account_number": account.get("ZLASTFOURDIGITS", ""),
                        "created_date": account.get("ZOBJECTCREATIONDATE", ""),
                    }
                )

        return accounts_data

    async def get_account(
        self, account_id: str, include_transactions: bool = False
    ) -> dict[str, Any]:
        """Get detailed account information."""
        # TODO: Implement full account details service
        # For now, return basic account info from list_accounts
        accounts = await self.list_accounts(include_hidden=True)
        for account in accounts:
            if account["id"] == account_id:
                if include_transactions:
                    # TODO: Add transaction history
                    account["recent_transactions"] = []
                return account

        raise ValueError(f"Account {account_id} not found")
