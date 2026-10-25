import pytest

from streamstats.errors import EventError
from streamstats.models import Event
from streamstats.parsers import parse_event, read_csv, read_jsonl

JSONL_LINE = (
    '{"timestamp": "2026-10-07T12:00:00+03:00", "level": "INFO", '
    '"source": "api", "message": "ok"}'
)
CSV_HEADER = "timestamp,level,source,message"
CSV_ROW = "2026-10-07T12:00:00+03:00,INFO,api,ok"


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------- read_jsonl ----------

def test_read_jsonl_yields_number_record_and_path(tmp_path):
    path = write(tmp_path, "a.jsonl", JSONL_LINE + "\n")

    records = list(read_jsonl(path))

    assert len(records) == 1
    number, record, record_path = records[0]
    assert number == 1
    assert record["source"] == "api"
    assert record_path == path


def test_read_jsonl_keeps_original_line_numbers(tmp_path):
    text = JSONL_LINE + "\n\n   \n" + JSONL_LINE + "\n"
    path = write(tmp_path, "a.jsonl", text)

    numbers = [number for number, _, _ in read_jsonl(path)]

    assert numbers == [1, 4]


def test_read_jsonl_empty_file(tmp_path):
    path = write(tmp_path, "empty.jsonl", "")

    assert list(read_jsonl(path)) == []


def test_read_jsonl_broken_line_raises_with_line_number(tmp_path):
    path = write(tmp_path, "a.jsonl", JSONL_LINE + "\n" + JSONL_LINE + "\n{broken\n")

    with pytest.raises(EventError, match="3"):
        list(read_jsonl(path))


def test_read_jsonl_skip_invalid_counts_broken_lines(tmp_path):
    text = JSONL_LINE + "\n{broken\n" + JSONL_LINE + "\n{also broken\n"
    path = write(tmp_path, "a.jsonl", text)
    counters = {"skipped": 0}

    records = list(read_jsonl(path, skip_invalid=True, counters=counters))

    assert [number for number, _, _ in records] == [1, 3]
    assert counters["skipped"] == 2


# ---------- read_csv ----------

def test_read_csv_yields_dicts(tmp_path):
    path = write(tmp_path, "a.csv", f"{CSV_HEADER}\n{CSV_ROW}\n")

    records = list(read_csv(path))

    assert len(records) == 1
    _number, record, record_path = records[0]
    assert record == {
        "timestamp": "2026-10-07T12:00:00+03:00",
        "level": "INFO",
        "source": "api",
        "message": "ok",
    }
    assert record_path == path


def test_read_csv_empty_file(tmp_path):
    path = write(tmp_path, "empty.csv", "")

    assert list(read_csv(path)) == []


def test_read_csv_header_only(tmp_path):
    path = write(tmp_path, "a.csv", CSV_HEADER + "\n")

    assert list(read_csv(path)) == []


def test_read_csv_quoted_comma_and_multiline_message(tmp_path):
    text = (
        f"{CSV_HEADER}\n"
        '2026-10-07T12:00:00+03:00,INFO,api,"a, b"\n'
        '2026-10-07T12:00:01+03:00,ERROR,db,"line 1\nline 2"\n'
        f"{CSV_ROW}\n"
    )
    path = write(tmp_path, "a.csv", text)

    records = list(read_csv(path))

    assert [record["message"] for _, record, _ in records] == [
        "a, b",
        "line 1\nline 2",
        "ok",
    ]


def test_read_csv_unicode(tmp_path):
    text = f"{CSV_HEADER}\n2026-10-07T12:00:00+03:00,INFO,база,café 日本語 🚀\n"
    path = write(tmp_path, "a.csv", text)

    _, record, _ = next(read_csv(path))

    assert record["source"] == "база"
    assert record["message"] == "café 日本語 🚀"


def test_read_csv_unclosed_quote_raises(tmp_path):
    text = f'{CSV_HEADER}\n2026-10-07T12:00:00+03:00,INFO,api,"never closed\n'
    path = write(tmp_path, "a.csv", text)

    with pytest.raises(EventError):
        list(read_csv(path))


# ---------- parse_event (stream of records -> events) ----------

def good_raw(**changes):
    raw = {
        "timestamp": "2026-10-07T12:00:00+03:00",
        "level": "INFO",
        "source": "api",
        "message": "ok",
    }
    raw.update(changes)
    return raw


def test_parse_event_turns_records_into_events():
    records = [(1, good_raw(), "f.jsonl"), (2, good_raw(source="db"), "f.jsonl")]

    events = list(parse_event(records))

    assert all(isinstance(event, Event) for event in events)
    assert [event.source for event in events] == ["api", "db"]


def test_parse_event_stops_and_reports_location():
    records = [(1, good_raw(), "f.jsonl"), (2, good_raw(level="LOUD"), "f.jsonl")]

    with pytest.raises(EventError, match="Event 2 at f.jsonl"):
        list(parse_event(records))


def test_parse_event_reports_bad_timestamp_with_location():
    records = [(7, good_raw(timestamp="вчера"), "f.jsonl")]

    with pytest.raises(EventError, match="Event 7 at f.jsonl"):
        list(parse_event(records))


def test_parse_event_skip_invalid_counts_and_continues():
    records = [
        (1, good_raw(), "f.jsonl"),
        (2, good_raw(level="LOUD"), "f.jsonl"),
        (3, good_raw(timestamp="вчера"), "f.jsonl"),
        (4, 42, "f.jsonl"),
        (5, good_raw(source="db"), "f.jsonl"),
    ]
    counters = {"skipped": 0}

    events = list(parse_event(records, skip_invalid=True, counters=counters))

    assert [event.source for event in events] == ["api", "db"]
    assert counters["skipped"] == 3


def test_parse_event_skip_invalid_writes_warning(caplog):
    records = [(2, good_raw(level="LOUD"), "f.jsonl")]

    with caplog.at_level("WARNING"):
        list(parse_event(records, skip_invalid=True, counters={"skipped": 0}))

    assert any(record.levelname == "WARNING" for record in caplog.records)
