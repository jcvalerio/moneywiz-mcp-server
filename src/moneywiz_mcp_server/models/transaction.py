"""Transaction data models for MoneyWiz MCP Server."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class TransactionType(Enum):
    """Transaction types based on MoneyWiz Core Data entities."""

    DEPOSIT = "deposit"  # ENT 37 - DepositTransaction
    WITHDRAW = "withdraw"  # ENT 47 - WithdrawTransaction
    TRANSFER_IN = "transfer_in"  # ENT 45 - TransferDepositTransaction
    TRANSFER_OUT = "transfer_out"  # ENT 46 - TransferWithdrawTransaction
    INVESTMENT_BUY = "investment_buy"  # ENT 40
    INVESTMENT_SELL = "investment_sell"  # ENT 41
    INVESTMENT_EXCHANGE = "investment_exchange"  # ENT 38
    REFUND = "refund"  # ENT 43
    RECONCILE = "reconcile"  # ENT 42
    TRANSFER_BUDGET = "transfer_budget"  # ENT 44
    UNKNOWN = "unknown"


@dataclass
class DateRange:
    """Date range for filtering transactions."""

    start_date: datetime
    end_date: datetime

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("Start date must be before end date")


@dataclass
class TransactionModel:
    """
    Unified transaction model based on MoneyWiz Core Data structure.

    Based on analysis of moneywiz-api/src/moneywiz_api/model/transaction.py:
    - All transaction entities use ZAMOUNT1 for the account-level amount
    - ZACCOUNT2 links transactions to accounts
    - ZDATE1 contains the transaction date
    - ZDESC2 contains the description
    """

    # Core transaction data from ZSYNCOBJECT
    id: str  # Z_PK as string
    entity_id: int  # Z_ENT (37, 45, 46, 47, etc.)
    account_id: int  # ZACCOUNT2

    # Transaction details
    amount: Decimal  # ZAMOUNT1 - account-level amount
    date: datetime  # ZDATE1
    description: str  # ZDESC2
    notes: str | None  # ZNOTES1
    reconciled: bool  # ZRECONCILED

    # Classification
    transaction_type: TransactionType
    category: str | None  # Category name (from entity mapping)
    category_id: int | None  # Category Z_PK
    parent_category: str | None  # Parent category name
    parent_category_id: int | None  # Parent category Z_PK
    category_path: str | None  # Full hierarchy "Food & Dining ▶ Groceries"
    category_hierarchy: list[str]  # ["Food & Dining", "Groceries"]
    payee: str | None  # Payee name (from entity mapping)
    payee_id: int | None  # ZPAYEE2

    # Currency information
    currency: str  # Account currency
    original_currency: str | None  # ZORIGINALCURRENCY
    original_amount: Decimal | None  # ZORIGINALAMOUNT
    exchange_rate: Decimal | None  # ZORIGINALEXCHANGERATE

    # Transfer-specific fields
    related_account_id: int | None = None  # For transfers
    related_transaction_id: int | None = None  # For transfers

    # Investment-specific fields
    investment_holding_id: int | None = None
    number_of_shares: Decimal | None = None
    price_per_share: Decimal | None = None
    fee: Decimal | None = None

    # Tags (populated by service enhancement)
    tags: list[str] = field(default_factory=list)  # Tag names from Z_36TAGS

    @classmethod
    def from_raw_data(cls, row: dict[str, Any]) -> "TransactionModel":
        """
        Create TransactionModel from raw Core Data row.

        Args:
            row: Raw ZSYNCOBJECT row data

        Returns:
            TransactionModel instance
        """
        entity_id = row.get("Z_ENT", 0)

        # Map entity to transaction type
        entity_type_map = {
            37: TransactionType.DEPOSIT,
            45: TransactionType.TRANSFER_IN,
            46: TransactionType.TRANSFER_OUT,
            47: TransactionType.WITHDRAW,
            40: TransactionType.INVESTMENT_BUY,
            41: TransactionType.INVESTMENT_SELL,
            38: TransactionType.INVESTMENT_EXCHANGE,
            43: TransactionType.REFUND,
            42: TransactionType.RECONCILE,
            44: TransactionType.TRANSFER_BUDGET,
        }

        transaction_type = entity_type_map.get(entity_id, TransactionType.UNKNOWN)

        # Convert date (Core Data timestamp to Python datetime)
        date_timestamp = row.get("ZDATE1", 0)
        if date_timestamp:
            # Core Data uses NSDate which is seconds since 2001-01-01
            base_date = datetime(2001, 1, 1)
            date = base_date.timestamp() + date_timestamp
            transaction_date = datetime.fromtimestamp(date)
        else:
            transaction_date = datetime.now()

        # Convert amounts to Decimal for precision
        amount = Decimal(str(row.get("ZAMOUNT1", 0)))
        original_amount = None
        if row.get("ZORIGINALAMOUNT"):
            original_amount = Decimal(str(row.get("ZORIGINALAMOUNT", 0)))

        exchange_rate = None
        if row.get("ZORIGINALEXCHANGERATE"):
            exchange_rate = Decimal(str(row.get("ZORIGINALEXCHANGERATE", 0)))

        return cls(
            id=str(row.get("Z_PK", "")),
            entity_id=entity_id,
            account_id=row.get("ZACCOUNT2", 0),
            amount=amount,
            date=transaction_date,
            description=row.get("ZDESC2", ""),
            notes=row.get("ZNOTES1"),
            reconciled=bool(row.get("ZRECONCILED", 0)),
            transaction_type=transaction_type,
            category=None,  # Will be resolved via ZCATEGORYASSIGMENT
            category_id=row.get(
                "ZCATEGORY2"
            ),  # Direct category reference or via ZCATEGORYASSIGMENT
            parent_category=None,  # Will be resolved with hierarchy
            parent_category_id=None,  # Will be resolved with hierarchy
            category_path=None,  # Will be built from hierarchy
            category_hierarchy=[],  # Will be built from hierarchy
            payee=None,  # Will be resolved separately
            payee_id=row.get("ZPAYEE2"),
            currency="USD",  # Will be resolved from account
            original_currency=row.get("ZORIGINALCURRENCY"),
            original_amount=original_amount,
            exchange_rate=exchange_rate,
            related_account_id=(
                row.get("ZSENDERACCOUNT") or row.get("ZRECIPIENTACCOUNT1")
            ),
            related_transaction_id=(
                row.get("ZSENDERTRANSACTION") or row.get("ZRECIPIENTTRANSACTION")
            ),
            investment_holding_id=row.get("ZINVESTMENTHOLDING"),
            number_of_shares=(
                Decimal(str(row.get("ZNUMBEROFSHARES1", 0)))
                if row.get("ZNUMBEROFSHARES1")
                else None
            ),
            price_per_share=(
                Decimal(str(row.get("ZPRICEPERSHARE1", 0)))
                if row.get("ZPRICEPERSHARE1")
                else None
            ),
            fee=(Decimal(str(row.get("ZFEE2", 0))) if row.get("ZFEE2") else None),
        )

    def is_expense(self) -> bool:
        """Check if transaction is an expense (negative amount)."""
        return self.amount < 0

    def is_income(self) -> bool:
        """Check if transaction is income (positive amount)."""
        return self.amount > 0

    def is_transfer(self) -> bool:
        """Check if transaction is a transfer between accounts."""
        return self.transaction_type in [
            TransactionType.TRANSFER_IN,
            TransactionType.TRANSFER_OUT,
        ]
