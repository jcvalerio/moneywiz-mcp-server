"""Input validation utilities for MoneyWiz MCP Server."""

import logging

logger = logging.getLogger(__name__)

# Valid account types supported by MoneyWiz
VALID_ACCOUNT_TYPES = [
    "checking",
    "savings",
    "credit_card",
    "investment",
    "cash",
    "loan",
    "property",
]

# Valid transaction types
VALID_TRANSACTION_TYPES = ["expense", "income", "transfer"]


def validate_account_type(account_type: str) -> bool:
    """Validate account type.

    Args:
        account_type: Account type to validate

    Returns:
        True if valid

    Raises:
        ValueError: If account type is invalid
    """
    if account_type.lower() not in VALID_ACCOUNT_TYPES:
        valid_types = ", ".join(VALID_ACCOUNT_TYPES)
        raise ValueError(
            f"Invalid account type '{account_type}'. Valid types: {valid_types}"
        )
    return True


def validate_transaction_type(transaction_type: str) -> bool:
    """Validate transaction type.

    Args:
        transaction_type: Transaction type to validate

    Returns:
        True if valid

    Raises:
        ValueError: If transaction type is invalid
    """
    if transaction_type.lower() not in VALID_TRANSACTION_TYPES:
        valid_types = ", ".join(VALID_TRANSACTION_TYPES)
        raise ValueError(
            f"Invalid transaction type '{transaction_type}'. Valid types: {valid_types}"
        )
    return True


def validate_amount(amount: float, transaction_type: str) -> bool:
    """Validate transaction amount.

    Args:
        amount: Amount to validate
        transaction_type: Type of transaction

    Returns:
        True if valid

    Raises:
        ValueError: If amount is invalid
    """
    if not isinstance(amount, int | float):
        raise ValueError("Amount must be a number")

    if amount == 0:
        raise ValueError("Amount cannot be zero")

    # For expense transactions, amount should be positive (will be negated)
    # For income transactions, amount should be positive
    # For transfers, amount should be positive
    if amount < 0 and transaction_type.lower() != "expense":
        raise ValueError(f"Amount must be positive for {transaction_type} transactions")

    return True


def validate_account_id(account_id: str) -> bool:
    """Validate account ID format.

    Args:
        account_id: Account ID to validate

    Returns:
        True if valid

    Raises:
        ValueError: If account ID is invalid
    """
    if not account_id or not isinstance(account_id, str):
        raise ValueError("Account ID must be a non-empty string")

    if len(account_id.strip()) == 0:
        raise ValueError("Account ID cannot be empty or whitespace")

    return True


def validate_currency_code(currency: str) -> bool:
    """Validate currency code.

    Args:
        currency: Currency code to validate (e.g., "USD", "EUR")

    Returns:
        True if valid

    Raises:
        ValueError: If currency code is invalid
    """
    if not currency or not isinstance(currency, str):
        raise ValueError("Currency code must be a non-empty string")

    if len(currency) != 3:
        raise ValueError("Currency code must be exactly 3 characters")

    if not currency.isalpha():
        raise ValueError("Currency code must contain only letters")

    return True


def validate_date_range(start_date: str | None, end_date: str | None) -> bool:
    """Validate date range.

    Args:
        start_date: Start date string
        end_date: End date string

    Returns:
        True if valid

    Raises:
        ValueError: If date range is invalid
    """
    from .formatters import parse_date

    if start_date and end_date:
        start = parse_date(start_date)
        end = parse_date(end_date)

        if start > end:
            raise ValueError("Start date must be before or equal to end date")

    return True


def validate_limit(limit: int | None, max_limit: int = 10000) -> bool:
    """Validate query limit parameter.

    Args:
        limit: Limit value to validate
        max_limit: Maximum allowed limit

    Returns:
        True if valid

    Raises:
        ValueError: If limit is invalid
    """
    if limit is not None:
        if not isinstance(limit, int):
            raise ValueError("Limit must be an integer")

        if limit <= 0:
            raise ValueError("Limit must be positive")

        if limit > max_limit:
            raise ValueError(f"Limit cannot exceed {max_limit}")

    return True
