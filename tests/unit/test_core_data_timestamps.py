"""Core Data timestamp conversion must not depend on the machine's timezone.

Core Data stores dates as seconds since 2001-01-01T00:00:00Z. Naive
datetimes in this codebase come from datetime.now() and are local time.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
import os
import time

import pytest

from moneywiz_mcp_server.models.transaction import TransactionModel
from moneywiz_mcp_server.services.budget_service import BudgetService
from moneywiz_mcp_server.services.scheduled_transaction_service import (
    ScheduledTransactionService,
)
from moneywiz_mcp_server.utils.date_utils import (
    core_data_timestamp_to_datetime,
    datetime_to_core_data_timestamp,
)

NSDATE_EPOCH = datetime(2001, 1, 1, tzinfo=UTC)
TIMEZONES = ["UTC", "America/Costa_Rica", "America/New_York", "Asia/Tokyo"]


def _core_data(utc_moment: datetime) -> float:
    """Independent oracle: seconds between the UTC epoch and a UTC moment."""
    return (utc_moment - NSDATE_EPOCH).total_seconds()


@pytest.fixture
def local_timezone() -> Iterator[Callable[[str], None]]:
    original = os.environ.get("TZ")

    def _set(name: str) -> None:
        os.environ["TZ"] = name
        time.tzset()

    yield _set
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


@pytest.mark.unit
class TestCoreDataTimestamps:
    def test_local_evening_maps_to_next_utc_day(self, local_timezone):
        # A transaction entered at 19:36:16 in Costa Rica (UTC-6) on Nov 1 is
        # stored by MoneyWiz at 01:36:16 UTC on Nov 2.
        local_timezone("America/Costa_Rica")
        local = datetime(2026, 11, 1, 19, 36, 16)
        stored = _core_data(datetime(2026, 11, 2, 1, 36, 16, tzinfo=UTC))

        assert datetime_to_core_data_timestamp(local) == pytest.approx(stored)
        assert core_data_timestamp_to_datetime(stored) == local

    @pytest.mark.parametrize("tz", TIMEZONES)
    def test_search_window_ending_now_includes_latest_entry(self, local_timezone, tz):
        # The bug: a window ending at datetime.now() ended hours in the past
        # for any non-UTC timezone, hiding the most recent transactions.
        local_timezone(tz)
        just_entered = datetime.now(UTC) - timedelta(minutes=5)

        end_of_window = datetime_to_core_data_timestamp(datetime.now())

        assert end_of_window >= _core_data(just_entered)
        assert end_of_window - _core_data(just_entered) < 600

    @pytest.mark.parametrize("tz", TIMEZONES)
    def test_round_trip_is_identity(self, local_timezone, tz):
        local_timezone(tz)
        # Includes a date on each side of US daylight-saving transitions
        for moment in (datetime(2026, 1, 15, 8, 30), datetime(2026, 7, 4, 23, 59, 59)):
            assert (
                core_data_timestamp_to_datetime(datetime_to_core_data_timestamp(moment))
                == moment
            )

    def test_aware_datetimes_use_their_own_timezone(self, local_timezone):
        local_timezone("Asia/Tokyo")
        moment = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

        assert datetime_to_core_data_timestamp(moment) == _core_data(moment)

    def test_transaction_dates_are_local_time(self, local_timezone):
        local_timezone("America/Costa_Rica")
        stored = _core_data(datetime(2026, 11, 2, 1, 36, 16, tzinfo=UTC))

        transaction = TransactionModel.from_raw_data({"Z_PK": 1, "ZDATE1": stored})

        assert transaction.date == datetime(2026, 11, 1, 19, 36, 16)

    def test_services_share_the_corrected_conversion(self, local_timezone):
        local_timezone("America/Costa_Rica")
        budget = BudgetService(db_manager=None)  # type: ignore[arg-type]
        scheduled = ScheduledTransactionService(db_manager=None)  # type: ignore[arg-type]
        local = datetime(2026, 11, 1, 19, 36, 16)
        stored = datetime_to_core_data_timestamp(local)

        assert budget._datetime_to_core_data_timestamp(local) == stored
        assert budget._core_data_timestamp_to_datetime(stored) == local
        assert scheduled._core_data_timestamp_to_datetime(stored) == local
