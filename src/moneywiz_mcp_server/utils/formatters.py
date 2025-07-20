"""Formatting utilities for MoneyWiz MCP Server."""

from datetime import date, datetime
import logging

from dateutil import parser

logger = logging.getLogger(__name__)


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format currency amount for display.

    Args:
        amount: Numeric amount to format
        currency: Currency code (e.g., "USD", "EUR")

    Returns:
        Formatted currency string

    Example:
        >>> format_currency(1234.56, "USD")
        "$1,234.56"
    """
    try:
        # Map common currency codes to symbols
        currency_symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "JPY": "¥",
            "CAD": "C$",
            "AUD": "A$",
        }

        symbol = currency_symbols.get(currency.upper(), currency)

        # Format with thousands separator and 2 decimal places
        if currency.upper() == "JPY":
            # Japanese Yen typically has no decimal places
            return f"{symbol}{amount:,.0f}"
        else:
            return f"{symbol}{amount:,.2f}"

    except Exception as e:
        logger.warning(f"Error formatting currency {amount} {currency}: {e}")
        return f"{currency} {amount:.2f}"


def parse_date(date_string: str) -> date:
    """Parse date string into date object.

    Args:
        date_string: Date string in various formats

    Returns:
        Parsed date object

    Raises:
        ValueError: If date string cannot be parsed

    Example:
        >>> parse_date("2024-01-15")
        date(2024, 1, 15)
        >>> parse_date("January 15, 2024")
        date(2024, 1, 15)
    """
    try:
        # Handle common date formats
        if isinstance(date_string, date):
            return date_string

        if isinstance(date_string, datetime):
            return date_string.date()

        # Parse string using dateutil parser
        parsed_dt = parser.parse(date_string)
        return parsed_dt.date()

    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse date '{date_string}': {e}")
        raise ValueError(f"Invalid date format: {date_string}")


def format_date(dt: date | datetime | str, format_str: str = "%Y-%m-%d") -> str:
    """Format date for consistent display.

    Args:
        dt: Date to format (date, datetime, or string)
        format_str: Output format string

    Returns:
        Formatted date string

    Example:
        >>> format_date(date(2024, 1, 15))
        "2024-01-15"
    """
    try:
        if isinstance(dt, str):
            dt = parse_date(dt)
        elif isinstance(dt, datetime):
            dt = dt.date()

        return dt.strftime(format_str)

    except Exception as e:
        logger.warning(f"Error formatting date {dt}: {e}")
        return str(dt)


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """Format percentage for display.

    Args:
        value: Percentage value (e.g., 0.15 for 15%)
        decimal_places: Number of decimal places

    Returns:
        Formatted percentage string

    Example:
        >>> format_percentage(0.1523)
        "15.23%"
    """
    try:
        return f"{value * 100:.{decimal_places}f}%"
    except Exception as e:
        logger.warning(f"Error formatting percentage {value}: {e}")
        return f"{value}%"
