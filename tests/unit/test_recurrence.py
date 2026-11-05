"""Tests for shared calendar recurrence arithmetic."""

from datetime import datetime
import logging

import pytest

from moneywiz_mcp_server.models.scheduled_transaction import RecurrencePattern
from moneywiz_mcp_server.utils.recurrence import (
    add_months,
    occurrence_dates,
    pattern_from_duration_unit,
    recurrence_from_duration,
    shift,
)

M = RecurrencePattern.MONTHLY
Y = RecurrencePattern.YEARLY
W = RecurrencePattern.WEEKLY
D = RecurrencePattern.DAILY


class TestDurationDecoding:
    @pytest.mark.parametrize(
        ("code", "pattern"),
        [(4, Y), (8, M), (16, D), (4096, W), (8192, W), (None, M)],
    )
    def test_ns_calendar_unit_codes(self, code, pattern):
        assert pattern_from_duration_unit(code) == pattern

    def test_unknown_code_warns_once_and_defaults_to_monthly(self, caplog):
        with caplog.at_level(logging.WARNING):
            assert pattern_from_duration_unit(999) == M
            assert pattern_from_duration_unit(999) == M
            assert pattern_from_duration_unit(998) == M
        assert caplog.text.count("unit 999") == 1
        assert "unit 998" in caplog.text

    @pytest.mark.parametrize(
        ("code", "count", "expected"),
        [
            (8, 1, (M, 1)),
            (8, 4, (M, 4)),
            (16, 7, (W, 1)),
            (16, 14, (W, 2)),
            (16, 3, (D, 3)),
            (8, None, (M, 1)),
            (8, 0, (M, 1)),
            (8, -2, (M, 1)),
        ],
    )
    def test_recurrence_from_duration(self, code, count, expected):
        assert recurrence_from_duration(code, count) == expected


class TestShift:
    @pytest.mark.parametrize(
        ("start", "pattern", "count", "expected"),
        [
            (datetime(2027, 1, 31), M, 1, datetime(2027, 2, 28)),
            (datetime(2028, 1, 31), M, 1, datetime(2028, 2, 29)),
            (datetime(2027, 1, 30), M, 1, datetime(2027, 2, 28)),
            (datetime(2027, 3, 31), M, 1, datetime(2027, 4, 30)),
            (datetime(2027, 12, 31), M, 1, datetime(2028, 1, 31)),
            (datetime(2028, 2, 29), Y, 1, datetime(2029, 2, 28)),
            (datetime(2028, 2, 29), Y, 4, datetime(2032, 2, 29)),
            (datetime(2027, 3, 31), M, -1, datetime(2027, 2, 28)),
            (datetime(2027, 1, 1), W, 2, datetime(2027, 1, 15)),
            (datetime(2027, 1, 1), D, 3, datetime(2027, 1, 4)),
        ],
    )
    def test_shift(self, start, pattern, count, expected):
        assert shift(start, pattern, count) == expected

    def test_add_months_keeps_time(self):
        assert add_months(datetime(2027, 1, 31, 9, 30), 1) == datetime(
            2027, 2, 28, 9, 30
        )


class TestOccurrenceDates:
    def test_month_end_does_not_drift(self):
        """Each date comes from the anchor, so the 31st returns after February."""
        dates = occurrence_dates(datetime(2027, 1, 31), M, limit=4)
        assert dates == [
            datetime(2027, 1, 31),
            datetime(2027, 2, 28),
            datetime(2027, 3, 31),
            datetime(2027, 4, 30),
        ]

    def test_leap_day_yearly(self):
        dates = occurrence_dates(datetime(2028, 2, 29), Y, limit=5)
        assert dates[1] == datetime(2029, 2, 28)
        assert dates[4] == datetime(2032, 2, 29)

    def test_interval(self):
        dates = occurrence_dates(datetime(2027, 1, 31), M, 4, limit=3)
        assert dates == [
            datetime(2027, 1, 31),
            datetime(2027, 5, 31),
            datetime(2027, 9, 30),
        ]

    def test_until_is_inclusive(self):
        dates = occurrence_dates(
            datetime(2027, 1, 1), W, 2, until=datetime(2027, 1, 29)
        )
        assert dates == [
            datetime(2027, 1, 1),
            datetime(2027, 1, 15),
            datetime(2027, 1, 29),
        ]

    def test_anchor_after_until_returns_nothing(self):
        assert (
            occurrence_dates(datetime(2027, 6, 1), M, until=datetime(2027, 1, 1)) == []
        )

    def test_requires_a_bound(self):
        with pytest.raises(ValueError):
            occurrence_dates(datetime(2027, 1, 1), D)
