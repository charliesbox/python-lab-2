import sys
import argparse

from .analyser import analyze
from .errors import StreamStatsError
from .parsers import parse_event, read_csv, read_jsonl

def build_parser():
    parser = argparse.ArgumentParser(
        prog="streamstats",
        description="Event stream analyzer for CSV and JSONL files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze", help="calculate statistics for event files"
    )
    analyze.add_argument(
        "files", nargs="+", help="one or more input files"
    )
    analyze.add_argument(
        "--format", required=True, choices=["csv", "jsonl"],
        help="format of the input files",
    )
    analyze.add_argument(
        "--output", default="report.json",
        help="path for the report file (default: report.json)",
    )
    analyze.add_argument(
        "--skip-invalid", action="store_true",
        help="skip invalid lines instead of stopping",
    )
    return parser

READERS = {"csv": read_csv, "jsonl": read_jsonl}

def read_all(paths, reader):
    for path in paths:
        yield from reader(path)


def main():
    args = build_parser().parse_args()
    reader = READERS[args.format]
    try:
        raw_records = read_all(args.files, reader)
        events = parse_event(raw_records)
        result = analyze(events)
    except StreamStatsError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(2)
    except OSError as error:
        print(f"Error: cannot read file: {error}", file=sys.stderr)
        sys.exit(2)
    print(result)


if __name__ == "__main__":
    main()
