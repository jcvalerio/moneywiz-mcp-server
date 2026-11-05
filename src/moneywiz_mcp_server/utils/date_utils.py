"""Date utility functions for MoneyWiz MCP Server."""

from datetime import datetime, timedelta
import re

from moneywiz_mcp_server.models.scheduled_transaction import RecurrencePattern
from moneywiz_mcp_server.models.transaction import DateRange
from moneywiz_mcp_server.utils.core_data_time import (
    core_data_timestamp_to_datetime,
    datetime_to_core_data_timestamp,
)
from moneywiz_mcp_server.utils.recurrence import shift

# MoneyWiz stores dates relative to 2001-01-01, so it holds no earlier data.
EARLIEST_DATE = datetime(2001, 1, 1)

SUPPORTED_TIME_PERIODS = (
    "'last N days|weeks|months|years' (or 'past ...'), 'last week|month|year', "
    "'this week|month|year', 'year to date', 'today', 'yesterday', 'all time'"
)

_RELATIVE_PERIOD = re.compile(
    r"(?:last|past) (?:(?P<count>\d+) )?(?P<unit>day|week|month|year)s?"
)


_PHRASE_UNITS = {
    "day": RecurrencePattern.DAILY,
    "week": RecurrencePattern.WEEKLY,
    "month": RecurrencePattern.MONTHLY,
    "year": RecurrencePattern.YEARLY,
}


def _go_back(now: datetime, count: int, unit: str) -> datetime:
    """Return now minus count units, never earlier than EARLIEST_DATE."""
    try:
        start = shift(now, _PHRASE_UNITS[unit], -count)
    except (ValueError, OverflowError):
        return EARLIEST_DATE
    return max(start, EARLIEST_DATE)


__all__ = [
    "EARLIEST_DATE",
    "SUPPORTED_TIME_PERIODS",
    "core_data_timestamp_to_datetime",
    "datetime_to_core_data_timestamp",
    "format_date_range_for_display",
    "get_date_range_from_days",
    "get_date_range_from_months",
    "parse_natural_language_date",
]


def get_date_range_from_months(months: int) -> DateRange:
    """
    Create a DateRange for the last N calendar months, ending now.

    Args:
        months: Number of months to go back

    Returns:
        DateRange covering the last N months
    """
    now = datetime.now()
    return DateRange(start_date=_go_back(now, months, "month"), end_date=now)


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


def parse_natural_language_date(text: str, now: datetime | None = None) -> DateRange:
    """
    Parse a time period phrase into a DateRange ending now.

    Supported phrases (case-insensitive):
        "last N days|weeks|months|years" (also "past ..."; N >= 1)
        "last day|week|month|year" (one unit)
        "this week|month|year", "year to date" / "ytd"
        "today", "yesterday", "all time"

    Months and years use calendar arithmetic, clamped at month ends.

    Args:
        text: Time period phrase, as passed by MCP tool callers
        now: Reference time; defaults to datetime.now()

    Returns:
        DateRange for the phrase

    Raises:
        ValueError: If the phrase is not supported. Unknown phrases are
            rejected rather than mapped to a default so callers never get a
            silently different period.
    """
    now = now or datetime.now()
    phrase = " ".join(text.lower().split())

    match = _RELATIVE_PERIOD.fullmatch(phrase)
    if match:
        count = int(match.group("count")) if match.group("count") else 1
        if count >= 1:
            return DateRange(
                start_date=_go_back(now, count, match.group("unit")), end_date=now
            )

    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if phrase == "today":
        return DateRange(start_date=start_of_today, end_date=now)
    if phrase == "yesterday":
        return DateRange(
            start_date=start_of_today - timedelta(days=1),
            end_date=start_of_today - timedelta(microseconds=1),
        )
    if phrase == "this week":
        return DateRange(
            start_date=start_of_today - timedelta(days=now.weekday()), end_date=now
        )
    if phrase == "this month":
        return DateRange(start_date=start_of_today.replace(day=1), end_date=now)
    if phrase in ("this year", "year to date", "ytd"):
        return DateRange(
            start_date=start_of_today.replace(month=1, day=1), end_date=now
        )
    if phrase == "all time":
        return DateRange(start_date=EARLIEST_DATE, end_date=now)

    raise ValueError(
        f"Unrecognized time period {text!r}. Supported: {SUPPORTED_TIME_PERIODS}"
    )


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
