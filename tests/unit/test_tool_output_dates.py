"""Every date a tool returns must be a valid RFC 3339 date-time.

FastMCP publishes each tool's output schema, and pydantic declares datetime
fields as ``"format": "date-time"``. RFC 3339 requires a UTC offset, but a
naive datetime serializes without one. Strict MCP clients (Claude Desktop)
validate structured output against the schema and reject the whole result,
while the Python MCP client does not check formats, so this would otherwise
only show up in the desktop app.
"""

from datetime import datetime
import typing

from pydantic import BaseModel, TypeAdapter
import pytest

from moneywiz_mcp_server.main import mcp

NAIVE = datetime(2027, 1, 31, 12, 0)


def _models_in(annotation: typing.Any) -> typing.Iterator[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
    for arg in typing.get_args(annotation):
        yield from _models_in(arg)


def _contains_datetime(annotation: typing.Any) -> bool:
    if annotation is datetime:
        return True
    return any(_contains_datetime(a) for a in typing.get_args(annotation))


def _tool_output_models() -> set[type[BaseModel]]:
    seen: set[type[BaseModel]] = set()
    pending = []
    for tool in mcp._tool_manager.list_tools():
        hints = typing.get_type_hints(tool.fn, include_extras=True)
        pending.extend(_models_in(hints.get("return")))
    while pending:
        model = pending.pop()
        if model in seen:
            continue
        seen.add(model)
        for field in model.model_fields.values():
            pending.extend(_models_in(field.annotation))
    return seen


def _datetime_fields() -> list[tuple[str, typing.Any]]:
    fields = []
    for model in _tool_output_models():
        for name, field in model.model_fields.items():
            if _contains_datetime(field.annotation):
                annotated = (
                    typing.Annotated[(field.annotation, *field.metadata)]
                    if field.metadata
                    else field.annotation
                )
                fields.append((f"{model.__name__}.{name}", annotated))
    return sorted(fields, key=lambda f: f[0])


def test_tool_output_models_are_discovered():
    names = {m.__name__ for m in _tool_output_models()}
    assert {"SalaryBreakdownResponse", "CommitmentBreakdown"} <= names


@pytest.mark.parametrize(
    ("field_name", "annotation"),
    _datetime_fields(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_datetime_fields_serialize_with_utc_offset(field_name, annotation):
    is_list = typing.get_origin(annotation) is list or (
        typing.get_origin(annotation) is typing.Annotated
        and typing.get_origin(typing.get_args(annotation)[0]) is list
    )
    sample = [NAIVE] if is_list else NAIVE
    value = TypeAdapter(annotation).dump_python(sample, mode="json")
    if is_list:
        value = value[0]
    assert isinstance(value, str), field_name
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None, f"{field_name} serialized as {value!r}"
    assert parsed.timestamp() == NAIVE.timestamp(), field_name


@pytest.mark.parametrize("tz", ["America/Costa_Rica", "Asia/Kolkata", "UTC"])
def test_naive_dates_get_the_local_offset(monkeypatch, tz):
    """Naive datetimes are local time; the offset must match the machine's
    zone, not UTC (CI runs in UTC, so set TZ explicitly)."""
    import time

    from moneywiz_mcp_server.models.scheduled_transaction import CommitmentBreakdown

    monkeypatch.setenv("TZ", tz)
    time.tzset()
    try:
        payload = CommitmentBreakdown(
            description="x",
            amount=1,
            currency="USD",
            category="c",
            next_date=NAIVE,
            payments_in_period=1,
            total_impact_in_period=1,
            commitment_type="infinite",
            urgency_level="regular",
        ).model_dump(mode="json")
        expected = {
            "America/Costa_Rica": "-06:00",
            "Asia/Kolkata": "+05:30",
            "UTC": "+00:00",
        }[tz]
        assert payload["next_date"] == f"2027-01-31T12:00:00{expected}"
        # Python-mode dumps keep real datetimes for internal callers.
        assert CommitmentBreakdown.model_validate(payload).next_date.tzinfo
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()
