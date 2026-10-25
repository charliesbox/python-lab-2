from datetime import datetime, timezone

from streamstats.analyser import analyze
from streamstats.models import Event, Level


def make_event(level=Level.info, source="api"):
    timestamp = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
    return Event(timestamp, level, source, "message")


def top5_as_lists(result):
    return [list(pair) for pair in result["top5"]]


def test_empty_stream():
    result = analyze(iter([]))

    assert result["total"] == 0
    assert result["levels"] == {}
    assert result["sources"] == {}
    assert result["top5"] == []


def test_counts_total_levels_and_sources():
    events = [
        make_event(Level.info, "api"),
        make_event(Level.info, "db"),
        make_event(Level.error, "db"),
        make_event(Level.debug, "api"),
    ]

    result = analyze(iter(events))

    assert result["total"] == 4
    assert result["levels"] == {"INFO": 2, "ERROR": 1, "DEBUG": 1}
    assert result["sources"] == {"api": 2, "db": 2}


def test_top5_counts_only_error_and_critical():
    events = [
        make_event(Level.error, "db"),
        make_event(Level.critical, "db"),
        make_event(Level.error, "api"),
        make_event(Level.warning, "cache"),
        make_event(Level.info, "cache"),
    ]

    result = analyze(iter(events))

    assert top5_as_lists(result) == [["db", 2], ["api", 1]]


def test_top5_is_limited_to_five_sources():
    events = [make_event(Level.error, f"s{i}") for i in range(8)]

    result = analyze(iter(events))

    assert len(result["top5"]) == 5


def test_top5_ties_are_sorted_alphabetically():
    events = (
        [make_event(Level.error, "db")] * 3
        + [make_event(Level.error, "payments")] * 2
        + [make_event(Level.error, "mailer")]
        + [make_event(Level.error, "auth")]
        + [make_event(Level.error, "cache")]
        + [make_event(Level.error, "loader")]
        + [make_event(Level.error, "api")]
    )

    result = analyze(iter(events))

    # db first, payments second; the five ties of 1 go in alphabetical order,
    # so "loader" and "mailer" do not make the top 5
    assert [source for source, _ in result["top5"]] == [
        "db",
        "payments",
        "api",
        "auth",
        "cache",
    ]


def test_analyze_consumes_a_generator_lazily():
    def generator():
        yield make_event(Level.info, "api")
        yield make_event(Level.error, "db")

    result = analyze(generator())

    assert result["total"] == 2
