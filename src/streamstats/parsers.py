import json
import csv
from datetime import datetime, timezone
from errors import EventError, TimestampError   #TODO: add relative import (.errors)
from models import Level, Event

def read_jsonl(path):
    with open(path, encoding="utf-8") as file:
        for number, line in enumerate(file, start=1):
            try:
                if line.strip() != "":
                    event = json.loads(line.strip())
                    yield number, event, path
            except json.JSONDecodeError:
                raise EventError(f"Jsonl event {number} log at {path} is broken.")


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        try:
            for line in reader:
                number = reader.line_num
                yield number, line, path
        except csv.Error:
            raise EventError(f"CSV event {reader.line_num} at {path} is broken.")


def parse_event(generator):
    for number, raw, path in generator:
        try:
            event = validate_event(raw)
        except EventError as error:
            raise EventError(f"Event {number} at {path} failed validation: {error}.")
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
        timestamp = datetime.fromisoformat(raw["timestamp"])
        if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
    except ValueError:
        raise TimestampError(f"The timestamp argument is broken: {raw['timestamp']}")


    if raw["source"].strip() == "":
        raise EventError("The log source must contain text")


    try:
        level = Level(raw["level"])
    except ValueError:
        raise EventError(f"Broken level log: {raw['level']}")

    return Event(timestamp, level, raw['source'], raw['message'])
