"""Tests for parse_natural_language_date.

The tools pass Claude's free-text time_period straight to this parser, so any
phrase it cannot handle must fail loudly instead of silently returning a
different window.
"""

from datetime import datetime

import pytest

from moneywiz_mcp_server.utils.date_utils import parse_natural_language_date

NOW = datetime(2026, 11, 2, 9, 30, 15)
MIDNIGHT = datetime(2026, 11, 2)


@pytest.mark.unit
class TestRelativePeriods:
    @pytest.mark.parametrize(
        ("phrase", "start"),
        [
            # Previously fell back to 3 months
            ("last 5 years", datetime(2021, 11, 2, 9, 30, 15)),
            ("past 2 years", datetime(2024, 11, 2, 9, 30, 15)),
            # Previously 1 month (no 3/6/12 in the text)
            ("last 2 months", datetime(2026, 9, 2, 9, 30, 15)),
            # Previously 3 months, because the text contains "3"
            ("last 13 months", datetime(2025, 10, 2, 9, 30, 15)),
            # Previously 7 days
            ("last 60 days", datetime(2026, 9, 3, 9, 30, 15)),
            ("last 14 days", datetime(2026, 10, 19, 9, 30, 15)),
            ("last 3 weeks", datetime(2026, 10, 12, 9, 30, 15)),
            # Calendar months, not 30-day blocks
            ("last 3 months", datetime(2026, 8, 2, 9, 30, 15)),
            ("last 12 months", datetime(2025, 11, 2, 9, 30, 15)),
            # Singular forms mean one unit
            ("last month", datetime(2026, 10, 2, 9, 30, 15)),
            ("last year", datetime(2025, 11, 2, 9, 30, 15)),
            ("last week", datetime(2026, 10, 26, 9, 30, 15)),
            ("past day", datetime(2026, 11, 1, 9, 30, 15)),
        ],
    )
    def test_relative_period_ends_now(self, phrase, start):
        date_range = parse_natural_language_date(phrase, now=NOW)

        assert date_range.start_date == start
        assert date_range.end_date == NOW

    def test_case_and_spacing_are_ignored(self):
        assert parse_natural_language_date(
            "  Last   5 YEARS ", now=NOW
        ) == parse_natural_language_date("last 5 years", now=NOW)

    def test_month_end_is_clamped(self):
        date_range = parse_natural_language_date(
            "last 1 month", now=datetime(2026, 3, 31, 12, 0)
        )

        assert date_range.start_date == datetime(2026, 2, 28, 12, 0)

    def test_leap_day_is_clamped(self):
        date_range = parse_natural_language_date(
            "last 1 year", now=datetime(2028, 2, 29, 12, 0)
        )

        assert date_range.start_date == datetime(2027, 2, 28, 12, 0)

    @pytest.mark.parametrize("phrase", ["last 200 years", "last 99999999999 days"])
    def test_huge_periods_start_at_core_data_epoch(self, phrase):
        # MoneyWiz cannot hold data before 2001-01-01, and very large values
        # must not overflow datetime arithmetic
        date_range = parse_natural_language_date(phrase, now=NOW)

        assert date_range.start_date == datetime(2001, 1, 1)
        assert date_range.end_date == NOW


@pytest.mark.unit
class TestCalendarPeriods:
    @pytest.mark.parametrize(
        ("phrase", "start", "end"),
        [
            ("today", MIDNIGHT, NOW),
            ("this week", datetime(2026, 11, 2), NOW),  # 2026-11-02 is a Monday
            ("this month", datetime(2026, 11, 1), NOW),
            ("this year", datetime(2026, 1, 1), NOW),
            ("year to date", datetime(2026, 1, 1), NOW),
            ("ytd", datetime(2026, 1, 1), NOW),
            ("all time", datetime(2001, 1, 1), NOW),
        ],
    )
    def test_calendar_period(self, phrase, start, end):
        date_range = parse_natural_language_date(phrase, now=NOW)

        assert date_range.start_date == start
        assert date_range.end_date == end

    def test_this_week_starts_on_monday(self):
        thursday = datetime(2026, 11, 5, 18, 0)

        date_range = parse_natural_language_date("this week", now=thursday)

        assert date_range.start_date == datetime(2026, 11, 2)

    def test_yesterday_is_the_whole_previous_day(self):
        date_range = parse_natural_language_date("yesterday", now=NOW)

        assert date_range.start_date == datetime(2026, 11, 1)
        assert date_range.end_date == datetime(2026, 11, 1, 23, 59, 59, 999999)


@pytest.mark.unit
class TestUnrecognizedPhrases:
    @pytest.mark.parametrize(
        "phrase",
        [
            "",
            "sometime",
            "last 0 months",
            "last -3 days",
            "next 6 months",
            "last 5 decades",
            "last 3 months and a bit",
        ],
    )
    def test_unrecognized_phrase_raises_with_supported_formats(self, phrase):
        with pytest.raises(ValueError, match="Supported") as error:
            parse_natural_language_date(phrase, now=NOW)

        assert "last N days|weeks|months|years" in str(error.value)

    def test_defaults_to_current_time(self):
        before = datetime.now()

        date_range = parse_natural_language_date("last 7 days")

        assert before <= date_range.end_date <= datetime.now()
