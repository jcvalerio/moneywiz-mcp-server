"""Tests for custom currency type Pydantic integration."""

from decimal import Decimal

from pydantic import BaseModel, TypeAdapter

from moneywiz_mcp_server.models.currency_types import CurrencyAmounts


class CurrencyModel(BaseModel):
    """Test model containing CurrencyAmounts."""

    amount: CurrencyAmounts


def test_currency_amounts_type_adapter_serializes_to_mapping() -> None:
    """CurrencyAmounts serializer returns a JSON-compatible mapping."""
    adapter = TypeAdapter(CurrencyAmounts)
    value = adapter.validate_python({"usd": Decimal("12.34")})

    assert adapter.dump_python(value) == {"USD": 12.34}
    assert adapter.dump_json(value) == b'{"USD":12.34}'


def test_currency_amounts_model_schema_and_dump() -> None:
    """Pydantic models expose JSON schema and serialize CurrencyAmounts fields."""
    schema = CurrencyModel.model_json_schema()
    model = CurrencyModel(amount=CurrencyAmounts({"CRC": Decimal("1234.56")}))

    assert schema["properties"]["amount"] == {
        "additionalProperties": {"type": "number"},
        "title": "Amount",
        "type": "object",
    }
    assert model.model_dump() == {"amount": {"CRC": 1234.56}}
    assert model.model_dump_json() == '{"amount":{"CRC":1234.56}}'
