"""Base models for MoneyWiz MCP Server responses."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, Field, PlainSerializer, field_serializer

from moneywiz_mcp_server.models.currency_types import CurrencyAmounts


def _to_rfc3339(value: datetime) -> str:
    """ISO 8601 with a UTC offset; naive values are taken as local time.

    Naive datetimes here come from core_data_timestamp_to_datetime, which
    returns local time, so astimezone() attaches the correct offset.
    """
    if value.tzinfo is None:
        value = value.astimezone()
    return value.isoformat()


# Use for every datetime field in a tool response model. Pydantic declares
# datetime as JSON Schema "date-time", which (RFC 3339) requires an offset;
# strict MCP clients such as Claude Desktop reject output that lacks one.
# tests/unit/test_tool_output_dates.py enforces this for all tool outputs.
ApiDateTime = Annotated[
    datetime, PlainSerializer(_to_rfc3339, return_type=str, when_used="json")
]


class BaseAnalysisResponse(BaseModel):
    """Base response model for all analysis endpoints."""

    analysis_period: str = Field(..., description="Time period analyzed (formatted)")
    currencies_found: list[str] = Field(
        ..., description="List of currencies found in the data"
    )
    primary_currency: str = Field(
        ..., description="Primary currency (highest activity)"
    )


class BaseCurrencyResponse(BaseModel):
    """Base response model for responses containing currency amounts."""

    @field_serializer("*", mode="wrap")
    def serialize_financial_types(self, value: Any, nxt: Any) -> Any:
        """Automatically convert CurrencyAmounts and Decimal values for JSON serialization."""
        # Handle CurrencyAmounts
        if isinstance(value, CurrencyAmounts):
            return value.to_json_dict()

        # Handle Decimal values
        if isinstance(value, Decimal):
            return float(value)

        # Handle dict with Decimal values
        if isinstance(value, dict) and all(
            isinstance(v, Decimal) for v in value.values()
        ):
            return {k: float(v) for k, v in value.items()}

        return nxt(value)


class FilterData(BaseModel):
    """Model for filter data in API responses."""

    include_hidden: bool | None = None
    account_type: str | None = None
    time_period: str | None = None
    account_ids: list[str] | None = None
    categories: list[str] | None = None
    transaction_type: str | None = None
    limit: int | None = None
