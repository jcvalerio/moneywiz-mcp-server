"""Calendar recurrence arithmetic shared by every service.

All "add N days/weeks/months/years" logic lives here so month-end and leap
day handling is implemented (and tested) once. Never use
``datetime.replace(month=...)`` or ``timedelta(days=30 * n)`` for calendar
math elsewhere: the first raises on the 29th-31st, the second drifts.
"""

from datetime import datetime
import logging

from dateutil.relativedelta import relativedelta

from moneywiz_mcp_server.models.scheduled_transaction import RecurrencePattern

logger = logging.getLogger(__name__)

# MoneyWiz stores recurrence units (ZDURATIONUNITS / ZDURATIONUNITS1) as
# Foundation NSCalendarUnit flags, with the count in ZDURATION / ZDURATION1.
# "Every 2 weeks" is typically stored as 14 days.
#
# Verified against a MoneyWiz 3 database: scheduled transactions use 4, 8 and
# 16 (16 with counts 7 and 14 for weekly/biweekly), budgets use 8. Codes 1 and
# 2 never occur; 2 is NSCalendarUnitEra and 1 is not a calendar unit, so the
# old 1=daily / 2=weekly mapping was a guess and is intentionally not kept.
NS_CALENDAR_UNIT_YEAR = 4
NS_CALENDAR_UNIT_MONTH = 8
NS_CALENDAR_UNIT_DAY = 16
NS_CALENDAR_UNIT_WEEK_OF_MONTH = 4096
NS_CALENDAR_UNIT_WEEK_OF_YEAR = 8192

DURATION_UNIT_PATTERNS: dict[int, RecurrencePattern] = {
    NS_CALENDAR_UNIT_YEAR: RecurrencePattern.YEARLY,
    NS_CALENDAR_UNIT_MONTH: RecurrencePattern.MONTHLY,
    NS_CALENDAR_UNIT_DAY: RecurrencePattern.DAILY,
    NS_CALENDAR_UNIT_WEEK_OF_MONTH: RecurrencePattern.WEEKLY,
    NS_CALENDAR_UNIT_WEEK_OF_YEAR: RecurrencePattern.WEEKLY,
}

DEFAULT_PATTERN = RecurrencePattern.MONTHLY

# Unknown codes already reported, so each is logged once per process rather
# than on every query.
_warned_unknown_codes: set[int] = set()


def pattern_from_duration_unit(code: int | None) -> RecurrencePattern:
    """Map a MoneyWiz duration unit code to a RecurrencePattern.

    Unknown codes fall back to monthly, with a warning (once per code) so the
    guess is visible.
    """
    if code is None:
        return DEFAULT_PATTERN
    pattern = DURATION_UNIT_PATTERNS.get(code)
    if pattern is None:
        if code not in _warned_unknown_codes:
            _warned_unknown_codes.add(code)
            logger.warning(
                f"Unknown MoneyWiz duration unit {code}; assuming {DEFAULT_PATTERN}"
            )
        return DEFAULT_PATTERN
    return pattern


def normalize_interval(interval: int | None) -> int:
    """Return a usable 'every N units' count (missing or < 1 means 1)."""
    if not isinstance(interval, int) or interval < 1:
        return 1
    return interval


def recurrence_from_duration(
    unit_code: int | None, count: int | None
) -> tuple[RecurrencePattern, int]:
    """Decode a MoneyWiz (duration unit, duration count) pair.

    Day-based schedules in whole weeks are reported as weekly, so "every
    14 days" becomes (WEEKLY, 2). The dates generated are identical.
    """
    pattern = pattern_from_duration_unit(unit_code)
    interval = normalize_interval(count)
    if pattern == RecurrencePattern.DAILY and interval % 7 == 0:
        return RecurrencePattern.WEEKLY, interval // 7
    return pattern, interval


def _delta(pattern: RecurrencePattern, count: int) -> relativedelta:
    if pattern == RecurrencePattern.DAILY:
        return relativedelta(days=count)
    if pattern == RecurrencePattern.WEEKLY:
        return relativedelta(weeks=count)
    if pattern == RecurrencePattern.MONTHLY:
        return relativedelta(months=count)
    return relativedelta(years=count)


def shift(anchor: datetime, pattern: RecurrencePattern, count: int) -> datetime:
    """Move anchor by count units (negative goes back).

    Months and years clamp to the last valid day: Jan 31 + 1 month is
    Feb 28/29, and Feb 29 + 1 year is Feb 28.
    """
    return anchor + _delta(pattern, count)


def add_months(anchor: datetime, months: int) -> datetime:
    """Calendar-month offset, clamped at month ends."""
    return shift(anchor, RecurrencePattern.MONTHLY, months)


def occurrence_dates(
    anchor: datetime,
    pattern: RecurrencePattern,
    interval: int = 1,
    *,
    until: datetime | None = None,
    limit: int | None = None,
) -> list[datetime]:
    """Dates of a recurring schedule starting at anchor (inclusive).

    Each date is computed from the anchor, not from the previous date, so a
    schedule on the 31st returns to the 31st after a short month.

    Args:
        anchor: First occurrence.
        pattern: Recurrence unit.
        interval: Every N units (values < 1 are treated as 1).
        until: Stop after this date (inclusive bound).
        limit: Maximum number of dates.
    """
    if until is None and limit is None:
        raise ValueError("occurrence_dates needs an until date or a limit")

    step = normalize_interval(interval)
    dates: list[datetime] = []
    k = 0
    while limit is None or len(dates) < limit:
        current = shift(anchor, pattern, k * step)
        if until is not None and current > until:
            break
        dates.append(current)
        k += 1
    return dates
