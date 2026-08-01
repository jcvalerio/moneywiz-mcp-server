"""Account service for MoneyWiz MCP Server."""

import logging
from typing import Any

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.services.transaction_service import (
    ACCOUNT_ENTITY_NAMES,
    TRANSACTION_TYPE_ENTITY_NAMES,
)

logger = logging.getLogger(__name__)


class AccountService:
    """Service for account operations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def list_accounts(
        self, include_hidden: bool = False, account_type: str | None = None
    ) -> list[dict[str, Any]]:
        """List all accounts with balances."""
        # Z_ENT ids are assigned per compiled Core Data model and are not
        # stable across MoneyWiz versions/exports - always resolve by name.
        entity_map = await self.db_manager.get_entity_name_map()
        account_entities = [
            entity_map[name] for name in ACCOUNT_ENTITY_NAMES if name in entity_map
        ]
        entity_types = {
            entity_map[name]: name for name in ACCOUNT_ENTITY_NAMES if name in entity_map
        }

        # Every transaction-family entity that can post an amount against an
        # account (deposits, withdrawals, transfers, refunds, investment
        # trades, ...) - the same set transaction_service.get_transactions()
        # resolves, so balance sums and transaction listings agree on what
        # counts as a transaction.
        transaction_entity_ids = [
            entity_map[name]
            for name in TRANSACTION_TYPE_ENTITY_NAMES.values()
            if name in entity_map
        ]
        txn_placeholders = ",".join("?" for _ in transaction_entity_ids)
        if not transaction_entity_ids:
            logger.warning(
                "No transaction entity ids resolved for this database - "
                "account balances will only reflect the opening balance"
            )

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
                balance_result = []
                if transaction_entity_ids:
                    # nosec: B608 - safe placeholder substitution
                    balance_query = (
                        "SELECT SUM(ZAMOUNT1) as total FROM ZSYNCOBJECT "
                        f"WHERE Z_ENT IN ({txn_placeholders}) AND ZACCOUNT2 = ?"
                    )
                    balance_result = await self.db_manager.execute_query(
                        balance_query, (*transaction_entity_ids, account["Z_PK"])
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
                        "entity_type": entity_name,
                        "last_updated": str(account.get("ZOBJECTCREATIONDATE", "")),
                        "archived": bool(account.get("ZARCHIVED", 0)),
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
