"""Conversion between Core Data timestamps and Python datetimes.

Core Data (NSDate) stores dates as seconds since 2001-01-01T00:00:00Z. This
module has no project imports so models and services can all share it.
"""

from datetime import datetime

# NSDate reference date (2001-01-01T00:00:00Z) as a Unix timestamp. Computing
# it from a naive datetime(2001, 1, 1) would apply the machine's UTC offset and
# shift every converted date by that many hours.
NSDATE_EPOCH_UNIX = 978_307_200.0


def core_data_timestamp_to_datetime(timestamp: float) -> datetime:
    """
    Convert Core Data timestamp to Python datetime.

    Args:
        timestamp: Seconds since 2001-01-01T00:00:00Z

    Returns:
        Naive datetime in the machine's local time, comparable with
        datetime.now()
    """
    return datetime.fromtimestamp(NSDATE_EPOCH_UNIX + timestamp)


def datetime_to_core_data_timestamp(dt: datetime) -> float:
    """
    Convert Python datetime to Core Data timestamp.

    Args:
        dt: Naive datetimes are interpreted as local time (as returned by
            datetime.now()); aware datetimes use their own timezone.

    Returns:
        Seconds since 2001-01-01T00:00:00Z
    """
    return dt.timestamp() - NSDATE_EPOCH_UNIX
