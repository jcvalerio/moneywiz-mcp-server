"""Date utility functions for MoneyWiz MCP Server."""

from datetime import datetime, timedelta

from moneywiz_mcp_server.models.transaction import DateRange


def get_date_range_from_months(months: int) -> DateRange:
    """
    Create a DateRange for the last N months.

    Args:
        months: Number of months to go back

    Returns:
        DateRange covering the last N months
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30)  # Approximate

    return DateRange(start_date=start_date, end_date=end_date)


def get_date_range_from_days(days: int) -> DateRange:
    """
    Create a DateRange for the last N days.

    Args:
        days: Number of days to go back

    Returns:
        DateRange covering the last N days
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    return DateRange(start_date=start_date, end_date=end_date)


def parse_natural_language_date(text: str) -> DateRange:
    """
    Parse natural language date expressions.

    Args:
        text: Natural language date expression

    Returns:
        DateRange corresponding to the expression

    Examples:
        "last 3 months" -> DateRange for last 3 months
        "last month" -> DateRange for last month
        "this year" -> DateRange for current year
    """
    text = text.lower().strip()

    if "last" in text and "month" in text:
        if "3" in text:
            return get_date_range_from_months(3)
        elif "6" in text:
            return get_date_range_from_months(6)
        elif "12" in text:
            return get_date_range_from_months(12)
        else:
            return get_date_range_from_months(1)

    elif "last" in text and "day" in text:
        if "30" in text:
            return get_date_range_from_days(30)
        elif "90" in text:
            return get_date_range_from_days(90)
        else:
            return get_date_range_from_days(7)

    elif "this year" in text:
        now = datetime.now()
        start_date = datetime(now.year, 1, 1)
        return DateRange(start_date=start_date, end_date=now)

    elif "this month" in text:
        now = datetime.now()
        start_date = datetime(now.year, now.month, 1)
        return DateRange(start_date=start_date, end_date=now)

    else:
        # Default to last 3 months
        return get_date_range_from_months(3)


def core_data_timestamp_to_datetime(timestamp: float) -> datetime:
    """
    Convert Core Data timestamp to Python datetime.

    Core Data uses NSDate which counts seconds since 2001-01-01 00:00:00 UTC.

    Args:
        timestamp: Core Data timestamp

    Returns:
        Python datetime object
    """
    # NSDate epoch: January 1, 2001 00:00:00 UTC
    nsdate_epoch = datetime(2001, 1, 1)
    return datetime.fromtimestamp(nsdate_epoch.timestamp() + timestamp)


def datetime_to_core_data_timestamp(dt: datetime) -> float:
    """
    Convert Python datetime to Core Data timestamp.

    Args:
        dt: Python datetime object

    Returns:
        Core Data timestamp
    """
    nsdate_epoch = datetime(2001, 1, 1)
    return dt.timestamp() - nsdate_epoch.timestamp()


def format_date_range_for_display(date_range: DateRange) -> str:
    """
    Format a DateRange for user display.

    Args:
        date_range: DateRange to format

    Returns:
        Human-readable date range string
    """
    start_str = date_range.start_date.strftime("%Y-%m-%d")
    end_str = date_range.end_date.strftime("%Y-%m-%d")

    return f"{start_str} to {end_str}"
