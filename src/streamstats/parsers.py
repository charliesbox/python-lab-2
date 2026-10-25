import csv
import json
import logging
from datetime import datetime, timezone

from .errors import EventError, TimestampError
from .models import Event, Level

logger = logging.getLogger(__name__)

def register_skip(counters, message):
    logger.warning(message)
    if counters is not None:
        counters["skipped"] += 1


def read_jsonl(path, skip_invalid=False, counters=None):
    with open(path, encoding="utf-8") as file:
        for number, line in enumerate(file, start=1):
            text = line.strip()
            if text == "":
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError:
                message = f"Jsonl event {number} log at {path} is broken."
                if not skip_invalid:
                    raise EventError(message)
                register_skip(counters, f"Skipped: {message}")
                continue
            yield number, record, path


def read_csv(path, skip_invalid=False, counters=None):
    # skip_invalid is accepted only so both readers have the same signature.
    # A broken CSV (e.g. an unclosed quote) cannot be skipped: it is unknown
    # where the next record starts.
    with open(path, encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        try:
            for line in reader:
                number = reader.line_num
                yield number, line, path
        except csv.Error:
            raise EventError(f"CSV event {reader.line_num} at {path} is broken.")


def parse_event(generator, skip_invalid=False, counters=None):
    for number, raw, path in generator:
        try:
            event = validate_event(raw)
        except (EventError, TimestampError) as error:
            message = f"Event {number} at {path} failed validation: {error}."
            if not skip_invalid:
                raise EventError(message)
            register_skip(counters, f"Skipped: {message}")
            continue
        yield event


def validate_event(raw):
    if not isinstance(raw, dict):
        raise EventError("The event log must be a valid log object")


    for field in ["timestamp", "level", "source", "message"]:
        if field not in raw or raw[field] is None:
            raise EventError(f"The object is missing a {field} argument")
        if not isinstance(raw[field], str):
            raise EventError(f"The {field} argument is broken")


    try:
        # this automatically convets the timezone into UTC time
        timestamp = datetime.fromisoformat(raw["timestamp"])
        if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc).astimezone(timezone.utc)
    except ValueError:
        raise TimestampError(f"The timestamp argument is broken: {raw['timestamp']}")


    if raw["source"].strip() == "":
        raise EventError("The log source must contain text")


    try:
        level = Level(raw["level"])
    except ValueError:
        raise EventError(f"Broken level log: {raw['level']}")

    return Event(timestamp, level, raw['source'], raw['message'])
