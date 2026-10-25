# Stream Analyzer

## Project Description

`streamstats` is a CLI utility that reads event files and builds a statistical report from them.
- `analyze` - reads one or more input files in CSV or JSONL format, validates every event, calculates statistics and saves them to a JSON report.

The utility processes the files as a stream: every file is read line by line, and only the running totals are stored in memory, never the events themselves. That is why it can handle files of any size.

## Idea and Infrastructure
The goal of the project is to build a small data-processing pipeline: **read → parse → validate → calculate → report**. Along the way we learn how to work with generators, custom exceptions, the `logging` module, `csv`/`json` and such python libraries as `argparse` and `pytest`.

## Project Structure
```
src/streamstats/
    __init__.py
    __main__.py     — entry point, argparse CLI, error handling
    errors.py       — custom exceptions
    models.py       — Level enum and Event dataclass
    parsers.py      — file readers (CSV, JSONL) and event validation
    analyser.py     — analyze(): statistics over a stream of events
    report.py       — write_report(): saves the result to a JSON file
tests/
    test_validation.py
    test_parsers.py
    test_analysis.py
    test_cli.py
data/
    events.csv      — example input (CSV)
    events.jsonl    — example input (JSONL)
pyproject.toml
```

## Input Formats

Every event consists of four fields:

| Field | Description |
|-------|-------------|
| `timestamp` | ISO 8601 date and time, e.g. `2026-10-07T12:00:00+03:00` |
| `level` | one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `source` | non-empty text, the component that produced the event |
| `message` | text |

**CSV** must have a header row with these four column names:
```
timestamp,level,source,message
2026-10-07T12:00:00+03:00,INFO,api,Request received
```
Quoted fields may contain commas and line breaks.

**JSONL** has one JSON object per line:
```
{"timestamp": "2026-10-07T12:00:00+03:00", "level": "INFO", "source": "api", "message": "Request received"}
```
Blank lines are ignored in both formats.

## How It Works

The pipeline looks like this:
```
data/events.csv
    |
    ▼
parsers.py: read_csv() / read_jsonl()
Generators. Read a file line by line and yield (line number, raw dict, path).
    |
    ▼
parsers.py: parse_event()
A generator. Takes the raw records and yields ready Event objects.
For every record calls validate_event().
    |
    ▼
parsers.py: validate_event()
Checks one raw dict: all fields are present and are strings,
the source is not empty, the level is known, the timestamp is valid.
Returns an Event or raises an error.
    |
    ▼
analyser.py: analyze()
Consumes the stream of events and keeps only counters.
    |
    ▼
report.py: write_report()
Saves the result as JSON.
    |
    ▼
__main__.py
The entry point of the CLI. Connects all the steps, summarizes several files
into one result and handles errors.
```

If several files are given, they are read one after another into a single stream, so the statistics are summed over all of them and are not reset between files.

### Report

The report is a JSON file (`report.json` by default):
```json
{
  "total": 45,
  "levels": {"INFO": 16, "DEBUG": 3, "WARNING": 5, "ERROR": 18, "CRITICAL": 3},
  "sources": {"loader": 6, "api": 7, "auth": 6, "db": 8, "cache": 6, "scheduler": 4, "mailer": 3, "payments": 5},
  "top5": [["db", 7], ["payments", 4], ["api", 3], ["auth", 2], ["cache", 2]],
  "earliest": "2026-10-07T08:30:00+00:00",
  "latest": "2026-10-07T12:15:00+00:00",
  "skipped": 0
}
```

| Key | Meaning |
|-----|---------|
| `total` | number of valid events |
| `levels` | number of events of every level |
| `sources` | number of events of every source |
| `top5` | five sources with the most `ERROR` and `CRITICAL` events, as `[source, count]` pairs |
| `earliest`, `latest` | the earliest and the latest event, in UTC (`null` if there were no events) |
| `skipped` | number of lines skipped because of `--skip-invalid` |

### Error handling
None of the modules just `sys.exit()` with a traceback in case of exceptions. Instead, they `raise` one of the custom exceptions. All of them inherit from `StreamStatsError`:

```
StreamStatsError
├── FormatError      — unsupported format
├── EventError       — invalid event
├── TimestampError   — invalid timestamp
└── CLIError         — invalid CLI configuration
```

`__main__.py` catches `StreamStatsError` (and `OSError`, for example when a file does not exist), prints the message to `stderr` and exits with the code `2`. The message contains the file and the line where the problem was found. `Exception` is never caught as a whole.

By default the first invalid line stops the processing. With `--skip-invalid` the line is skipped, a `WARNING` is written to the log, and the counter of skipped lines goes to the report. The valid lines after the error are still counted.

### Design decisions
- **Time zones.** All timestamps are converted to UTC. A timestamp without a time zone is considered to be in UTC.
- **Levels are case-sensitive.** `INFO` is valid, `info` is not.
- **Ties in the top 5.** Sources with the same number of errors are sorted alphabetically.
- **Line numbers.** For JSONL it is the line number in the file. For CSV it is the line where the record ends, so a record with a line break inside it may have a larger number than expected.
- **Broken CSV cannot be skipped.** If a CSV file has an unclosed quote, it is unknown where the next record starts, so this error always stops the processing, even with `--skip-invalid`. In JSONL every line is independent, so broken lines can be skipped.
- **One format per run.** `--format` applies to all the files of a single run.

## Testing
60 pytest tests (27 for the event validation, 16 for the readers and the parsing stream, 6 for the analyzer, 11 for the CLI) covering both successful scenarios and the error cases: missing fields, wrong types, empty source, unknown level, broken timestamps, empty files, broken lines in both modes, several files, Unicode and the exit codes of the CLI.

```bash
python -m pytest
ruff check .
```

## Installation and Usage

### Clone the repository to your machine
```bash
git clone <repository-url>
cd <repository-folder>
```

### Set up the virtual environment and dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest ruff
```

### Usage
```bash
python -m streamstats analyze data/events.csv --format csv --output report.json
python -m streamstats analyze a.jsonl b.jsonl --format jsonl --skip-invalid
python -m streamstats --help
```

| Argument | Description |
|----------|-------------|
| `files` | one or more input files |
| `--format` | `csv` or `jsonl` (required) |
| `--output` | path of the report file, `report.json` by default |
| `--skip-invalid` | skip invalid lines instead of stopping |

If the package is not installed with `pip install -e .`, navigate to the `src` directory first and run the same commands from there:
```bash
cd src
python -m streamstats analyze ../data/events.csv --format csv
```
