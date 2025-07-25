"""Base models for MoneyWiz MCP Server responses."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_serializer

from moneywiz_mcp_server.models.currency_types import CurrencyAmounts


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
