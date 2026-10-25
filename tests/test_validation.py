from datetime import datetime, timezone

import pytest

from streamstats.errors import EventError, TimestampError
from streamstats.models import Event, Level
from streamstats.parsers import validate_event


def make_raw(**changes):
    raw = {
        "timestamp": "2026-10-07T12:00:00+03:00",
        "level": "INFO",
        "source": "api",
        "message": "Hello",
    }
    raw.update(changes)
    return raw


def test_valid_event_is_converted_to_event():
    event = validate_event(make_raw())

    assert isinstance(event, Event)
    assert event.level == Level.info
    assert event.source == "api"
    assert event.message == "Hello"
    # 12:00 in +03:00 is 09:00 UTC (aware datetimes compare by the moment)
    assert event.timestamp == datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


def test_timestamp_without_timezone_is_treated_as_utc():
    event = validate_event(make_raw(timestamp="2026-10-07T12:00:00"))

    assert event.timestamp == datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("field", ["timestamp", "level", "source", "message"])
def test_missing_field_raises(field):
    raw = make_raw()
    del raw[field]

    with pytest.raises(EventError, match=field):
        validate_event(raw)


@pytest.mark.parametrize("field", ["timestamp", "level", "source", "message"])
def test_none_value_raises(field):
    with pytest.raises(EventError):
        validate_event(make_raw(**{field: None}))


@pytest.mark.parametrize("value", [5, 1.5, ["a"], {"a": 1}, True])
def test_non_string_value_raises(value):
    with pytest.raises(EventError):
        validate_event(make_raw(source=value))


@pytest.mark.parametrize("source", ["", "   ", "\t"])
def test_blank_source_raises(source):
    with pytest.raises(EventError):
        validate_event(make_raw(source=source))


def test_unknown_level_raises():
    with pytest.raises(EventError, match="LOUD"):
        validate_event(make_raw(level="LOUD"))


def test_level_is_case_sensitive():
    # strict choice: only exact upper-case level names are accepted
    with pytest.raises(EventError):
        validate_event(make_raw(level="info"))


@pytest.mark.parametrize("timestamp", ["вчера", "2026-13-45", "12:00"])
def test_broken_timestamp_raises_timestamp_error(timestamp):
    with pytest.raises(TimestampError):
        validate_event(make_raw(timestamp=timestamp))


@pytest.mark.parametrize("raw", [42, [1, 2], "text", None])
def test_not_an_object_raises(raw):
    with pytest.raises(EventError):
        validate_event(raw)
