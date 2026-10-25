import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

CSV_HEADER = "timestamp,level,source,message"


def run_cli(*args, cwd):
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, "-m", "streamstats", *map(str, args)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env=env,
    )


def write_csv(path, rows):
    path.write_text(CSV_HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def load_report(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_help_works(tmp_path):
    result = run_cli("--help", cwd=tmp_path)

    assert result.returncode == 0
    assert "analyze" in result.stdout


def test_analyze_csv_writes_report(tmp_path):
    source = write_csv(
        tmp_path / "a.csv",
        [
            "2026-10-07T12:00:00+03:00,INFO,api,ok",
            "2026-10-07T12:00:01+03:00,ERROR,db,fail",
            "2026-10-07T12:00:02+03:00,CRITICAL,db,fail",
        ],
    )
    report_path = tmp_path / "report.json"

    result = run_cli(
        "analyze", source, "--format", "csv", "--output", report_path, cwd=tmp_path
    )

    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    report = load_report(report_path)
    assert report["total"] == 3
    assert report["levels"] == {"INFO": 1, "ERROR": 1, "CRITICAL": 1}
    assert report["sources"] == {"api": 1, "db": 2}
    assert [list(pair) for pair in report["top5"]] == [["db", 2]]
    assert report["skipped"] == 0


def test_analyze_jsonl(tmp_path):
    line = (
        '{"timestamp": "2026-10-07T12:00:00+03:00", "level": "WARNING", '
        '"source": "api", "message": "slow"}'
    )
    source = tmp_path / "a.jsonl"
    source.write_text(line + "\n" + line + "\n", encoding="utf-8")
    report_path = tmp_path / "report.json"

    result = run_cli(
        "analyze", source, "--format", "jsonl", "--output", report_path, cwd=tmp_path
    )

    assert result.returncode == 0
    assert load_report(report_path)["levels"] == {"WARNING": 2}


def test_results_are_summed_across_files(tmp_path):
    first = write_csv(tmp_path / "a.csv", ["2026-10-07T12:00:00+03:00,ERROR,db,x"])
    second = write_csv(
        tmp_path / "b.csv",
        [
            "2026-10-07T12:00:01+03:00,ERROR,db,x",
            "2026-10-07T12:00:02+03:00,INFO,api,x",
        ],
    )
    report_path = tmp_path / "report.json"

    result = run_cli(
        "analyze",
        first,
        second,
        "--format",
        "csv",
        "--output",
        report_path,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    report = load_report(report_path)
    assert report["total"] == 3
    assert report["sources"] == {"db": 2, "api": 1}
    assert [list(pair) for pair in report["top5"]] == [["db", 2]]


def test_earliest_and_latest_compare_real_moments(tmp_path):
    source = write_csv(
        tmp_path / "a.csv",
        [
            # 09:00 UTC
            "2026-10-07T09:00:00+00:00,INFO,api,x",
            # 08:30 UTC: earliest, although its text sorts after the line above
            "2026-10-07T11:30:00+03:00,INFO,api,x",
            # 12:15 UTC: latest, although its text sorts before the others
            "2026-10-07T07:15:00-05:00,INFO,api,x",
        ],
    )
    report_path = tmp_path / "report.json"

    run_cli("analyze", source, "--format", "csv", "--output", report_path, cwd=tmp_path)

    report = load_report(report_path)
    earliest = datetime.fromisoformat(report["earliest"])
    latest = datetime.fromisoformat(report["latest"])
    assert earliest == datetime(2026, 10, 7, 8, 30, tzinfo=timezone.utc)
    assert latest == datetime(2026, 10, 7, 12, 15, tzinfo=timezone.utc)


def test_unicode_is_kept_readable_in_report(tmp_path):
    source = write_csv(
        tmp_path / "a.csv",
        ["2026-10-07T12:00:00+03:00,ERROR,база,Не удалось подключиться 🚀"],
    )
    report_path = tmp_path / "report.json"

    result = run_cli(
        "analyze", source, "--format", "csv", "--output", report_path, cwd=tmp_path
    )

    assert result.returncode == 0
    text = report_path.read_text(encoding="utf-8")
    assert "база" in text
    assert "\\u" not in text


def test_invalid_line_stops_with_code_2(tmp_path):
    source = write_csv(
        tmp_path / "bad.csv",
        [
            "2026-10-07T12:00:00+03:00,INFO,api,ok",
            "2026-10-07T12:00:01+03:00,LOUD,api,bad level",
        ],
    )
    report_path = tmp_path / "report.json"

    result = run_cli(
        "analyze", source, "--format", "csv", "--output", report_path, cwd=tmp_path
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "bad.csv" in result.stderr
    assert "3" in result.stderr


def test_skip_invalid_continues_and_counts(tmp_path):
    source = write_csv(
        tmp_path / "bad.csv",
        [
            "2026-10-07T12:00:00+03:00,INFO,api,ok",
            "2026-10-07T12:00:01+03:00,LOUD,api,bad level",
            "вчера,INFO,api,bad time",
            "2026-10-07T12:00:03+03:00,ERROR,db,ok",
        ],
    )
    report_path = tmp_path / "report.json"

    result = run_cli(
        "analyze",
        source,
        "--format",
        "csv",
        "--skip-invalid",
        "--output",
        report_path,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "WARNING" in result.stderr
    report = load_report(report_path)
    assert report["total"] == 2
    assert report["skipped"] == 2


def test_missing_input_file_gives_code_2(tmp_path):
    result = run_cli(
        "analyze", tmp_path / "nope.csv", "--format", "csv", cwd=tmp_path
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_empty_input_file_gives_empty_report(tmp_path):
    source = tmp_path / "empty.csv"
    source.write_text("", encoding="utf-8")
    report_path = tmp_path / "report.json"

    result = run_cli(
        "analyze", source, "--format", "csv", "--output", report_path, cwd=tmp_path
    )

    assert result.returncode == 0
    report = load_report(report_path)
    assert report["total"] == 0
    assert report["levels"] == {}


def test_unsupported_format_gives_code_2(tmp_path):
    source = write_csv(tmp_path / "a.csv", ["2026-10-07T12:00:00+03:00,INFO,api,ok"])

    result = run_cli("analyze", source, "--format", "xml", cwd=tmp_path)

    assert result.returncode == 2
