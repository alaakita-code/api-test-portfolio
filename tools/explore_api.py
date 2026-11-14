"""Record what the API really returns, one timestamped record per run.

This is an observation tool, not a test. It makes no pass/fail judgement.
Use it before writing tests, or whenever the API may have changed.

Each run sends the requests listed in PROBES and writes two sets of files:

Public record (safe to commit) in docs/observations/
    observed_<UTC time>.md     readable record of the run
    observed_<UTC time>.json   same data, used for comparison by the next run
    INDEX.md                   one row per run, linking to each record
    Contains API data and library versions only. Headers that vary per
    request or carry tracking values are left out, failed requests keep
    only the error type, and times are in UTC.

Full local record (never committed) in observations_local/
    observed_<UTC time>_full.md   everything needed for troubleshooting
    INDEX.md                      one row per run
    Contains all response headers, full error messages, complete bodies,
    the local time and details of the machine that ran the tool.
    The folder is listed in .gitignore.

Privacy is enforced where data leaves the machine, not where it is created:
the full record stays local for diagnosis and only the public record is
published. Nothing is overwritten, so earlier records are kept as history.
The result is compared with the previous run and any change is listed.

Usage:
    .\\.venv\\Scripts\\python.exe tools/explore_api.py
"""

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# Make "utils" importable when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.config import BASE_URL, TIMEOUT_SECONDS  # noqa: E402

# Public record: committed to the repository.
OUTPUT_DIR = PROJECT_ROOT / "docs" / "observations"
INDEX_FILE = OUTPUT_DIR / "INDEX.md"

# Full local record: listed in .gitignore, never committed.
LOCAL_DIR = PROJECT_ROOT / "observations_local"
LOCAL_INDEX_FILE = LOCAL_DIR / "INDEX.md"

# Response headers kept in the public record. Headers that change on every
# request or carry tracking values (Date, Age, CF-RAY, Report-To) are left
# out there. The full local record keeps every header.
RECORDED_HEADERS = ["Content-Type", "Cache-Control", "cf-cache-status", "Location"]

# Longest response body kept in the public record, in characters.
# The full local record keeps the complete body.
MAX_BODY_CHARS = 1000

NEW_POST = {"title": "foo", "body": "bar", "userId": 1}

# (group, method, path, request body, question this probe answers)
PROBES = [
    ("positive", "GET", "/posts", None, "list: how many items?"),
    ("positive", "GET", "/posts/1", None, "single item: which fields?"),
    ("positive", "GET", "/posts?userId=1", None, "filter by userId"),
    ("positive", "GET", "/posts/1/comments", None, "nested route"),
    ("positive", "POST", "/posts", NEW_POST, "create: status and returned id?"),
    ("positive", "PUT", "/posts/1", {"id": 1, "title": "t", "body": "b", "userId": 1}, "full update"),
    ("positive", "PATCH", "/posts/1", {"title": "patched"}, "partial update"),
    ("positive", "DELETE", "/posts/1", None, "delete: status and body?"),
    ("boundary", "GET", "/posts/100", None, "last valid id"),
    ("boundary", "GET", "/posts/0", None, "just below the first id"),
    ("boundary", "GET", "/posts/101", None, "just above the last id"),
    ("boundary", "GET", "/posts/-1", None, "negative id"),
    ("boundary", "GET", "/posts/abc", None, "non-numeric id"),
    ("negative", "GET", "/not-a-real-path", None, "unknown path"),
    ("negative", "GET", "/posts?userId=999", None, "filter with no match"),
    ("negative", "POST", "/posts", {}, "empty body: is it rejected?"),
    ("negative", "PUT", "/posts/101", {"title": "x"}, "update an id that does not exist"),
    ("negative", "DELETE", "/posts/101", None, "delete an id that does not exist"),
    ("repeat", "GET", "/posts/1", None, "same GET again: same result?"),
    ("repeat", "DELETE", "/posts/1", None, "same DELETE again: same result?"),
]


def summarize_body(response):
    """Describe the response body in one short, comparable line."""
    try:
        data = response.json()
    except ValueError:
        return "not JSON"
    if isinstance(data, list):
        if not data:
            return "empty list"
        first = data[0]
        keys = ", ".join(first.keys()) if isinstance(first, dict) else type(first).__name__
        return "list of %d; item keys: %s" % (len(data), keys)
    if isinstance(data, dict):
        if not data:
            return "empty object"
        return "object; keys: %s" % ", ".join(data.keys())
    return type(data).__name__


def run_probes():
    """Send every probe and return one full record (a dict) per request.

    A full record holds everything observed. to_public_record() later
    derives the reduced version that is safe to publish.
    """
    records = []
    for number, (group, method, path, body, question) in enumerate(PROBES, start=1):
        record = {
            "number": number,
            "group": group,
            "method": method,
            "path": path,
            "sent": body,
            "question": question,
        }
        try:
            response = requests.request(method, BASE_URL + path, json=body, timeout=TIMEOUT_SECONDS)
            record["status"] = response.status_code
            record["seconds"] = round(response.elapsed.total_seconds(), 3)
            record["summary"] = summarize_body(response)
            record["headers"] = dict(response.headers)
            record["body"] = response.text
            record["error"] = ""
        except requests.RequestException as error:
            # A failed request is recorded, not hidden.
            record["status"] = "ERROR"
            record["seconds"] = None
            record["summary"] = type(error).__name__
            record["headers"] = {}
            record["body"] = ""
            record["error"] = str(error)
        records.append(record)
        print("%2d  %-8s %-6s %-22s -> %s" % (number, group, method, path, record["status"]))
    return records


def to_public_record(record):
    """Return a copy of a full record that is safe to publish.

    Keeps only the allow-listed headers, shortens long bodies and drops the
    error message, which can include local network details such as proxy
    addresses. The error type stays available in "summary".
    """
    public = {key: record[key] for key in
              ("number", "group", "method", "path", "sent", "question", "status", "seconds", "summary")}
    public["headers"] = {
        name: record["headers"][name] for name in RECORDED_HEADERS if name in record["headers"]
    }
    body = record["body"]
    public["body"] = body if len(body) <= MAX_BODY_CHARS else body[:MAX_BODY_CHARS] + "\n... (truncated)"
    return public


def load_previous_run():
    """Return (file name, records) of the latest earlier run, or (None, None)."""
    earlier = sorted(OUTPUT_DIR.glob("observed_*.json"))
    if not earlier:
        return None, None
    latest = earlier[-1]
    with open(latest, encoding="utf-8") as handle:
        return latest.name, json.load(handle)["records"]


def find_changes(previous, current):
    """List differences in status or body summary between two runs.

    Response times are not compared, because they vary on every run.
    """
    before = {(r["number"], r["method"], r["path"]): r for r in previous}
    changes = []
    for record in current:
        key = (record["number"], record["method"], record["path"])
        label = "#%d %s %s" % key
        old = before.get(key)
        if old is None:
            changes.append("%s: new probe, no earlier result" % label)
            continue
        if old["status"] != record["status"]:
            changes.append("%s: status %s -> %s" % (label, old["status"], record["status"]))
        if old["summary"] != record["summary"]:
            changes.append("%s: body '%s' -> '%s'" % (label, old["summary"], record["summary"]))
    return changes


def count_statuses(records):
    """Return a short text such as '200 x11, 201 x2, 404 x7'."""
    counts = {}
    for record in records:
        counts[str(record["status"])] = counts.get(str(record["status"]), 0) + 1
    return ", ".join("%s x%d" % (status, counts[status]) for status in sorted(counts))


def cell(text):
    """Make a value safe to place inside a Markdown table cell."""
    return str(text).replace("|", "/").replace("\n", " ")


def write_detail_file(path, run_time, records, previous_name, changes):
    """Write the full, human-readable record of one run."""
    timed = [r["seconds"] for r in records if r["seconds"] is not None]
    lines = [
        "# API observation %s" % run_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "",
        "Generated by `tools/explore_api.py`. Observation only; no pass/fail judgement.",
        "This is the public record. Tracking headers, error messages and machine",
        "details are kept only in the local record under `observations_local/`.",
        "",
        "## Run information",
        "",
        "| Item | Value |",
        "|---|---|",
        "| Base URL | %s |" % BASE_URL,
        "| Client | Python %s, requests %s |" % (platform.python_version(), requests.__version__),
        "| Timeout per request | %s seconds |" % TIMEOUT_SECONDS,
        "| Requests sent | %d |" % len(records),
        "| Status codes | %s |" % count_statuses(records),
    ]
    if timed:
        lines.append(
            "| Response time | min %.3f s, max %.3f s, average %.3f s |"
            % (min(timed), max(timed), sum(timed) / len(timed))
        )
    lines += ["", "## Changes since the previous run", ""]
    if previous_name is None:
        lines.append("No earlier run to compare with. This is the baseline.")
    elif not changes:
        lines.append("No change in status codes or body structure compared with `%s`." % previous_name)
    else:
        lines.append("Compared with `%s`:" % previous_name)
        lines.append("")
        lines += ["- %s" % change for change in changes]
        lines += ["", "Review these before changing any test. See the usage manual, section 8.3."]

    lines += [
        "",
        "## Summary table",
        "",
        "| # | Group | Method | Path | Status | Seconds | Body | Question |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        seconds = "-" if r["seconds"] is None else "%.3f" % r["seconds"]
        lines.append(
            "| %d | %s | %s | %s | %s | %s | %s | %s |"
            % (r["number"], r["group"], r["method"], cell(r["path"]), r["status"], seconds,
               cell(r["summary"]), cell(r["question"]))
        )

    lines += ["", "## Details", ""]
    for r in records:
        lines += ["### #%d %s %s" % (r["number"], r["method"], r["path"]), ""]
        lines.append("- Question: %s" % r["question"])
        lines.append("- Sent body: %s" % ("none" if r["sent"] is None else "`%s`" % json.dumps(r["sent"])))
        lines.append("- Status: %s" % r["status"])
        for name, value in r["headers"].items():
            lines.append("- %s: `%s`" % (name, value))
        if r["body"]:
            lines += ["", "```", r["body"], "```"]
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_data_file(path, run_time, records):
    """Write the same data as JSON so the next run can compare against it."""
    data = {
        "run_time_utc": run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE_URL,
        "records": records,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def update_index(run_time, records, detail_name, previous_name, changes):
    """Add one row for this run to the index, creating the index if needed."""
    if not INDEX_FILE.exists():
        header = [
            "# API observation index",
            "",
            "One row per run of `tools/explore_api.py`, oldest first.",
            "Open the detail file for the full record of a run.",
            "",
            "| Run time (UTC) | Requests | Status codes | Errors | Changes vs previous run | Detail |",
            "|---|---|---|---|---|---|",
        ]
        INDEX_FILE.write_text("\n".join(header) + "\n", encoding="utf-8")

    errors = sum(1 for r in records if r["status"] == "ERROR")
    if previous_name is None:
        change_text = "baseline"
    elif not changes:
        change_text = "none"
    else:
        change_text = "%d change(s)" % len(changes)
    row = "| %s | %d | %s | %d | %s | [%s](%s) |\n" % (
        run_time.strftime("%Y-%m-%d %H:%M:%S"), len(records), count_statuses(records),
        errors, change_text, detail_name, detail_name,
    )
    with open(INDEX_FILE, "a", encoding="utf-8") as handle:
        handle.write(row)


def write_local_detail_file(path, run_time, records, public_name, previous_name, changes):
    """Write the full record of one run for local troubleshooting.

    Unlike the public record, this keeps every response header, the full
    error message, the complete body, the local time and machine details.
    """
    local_time = run_time.astimezone()
    lines = [
        "# API observation %s (full local record)" % run_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "",
        "LOCAL USE ONLY. This file contains machine and network details.",
        "It is excluded from version control by .gitignore. Do not publish it.",
        "The publishable version of this run is `docs/observations/%s`." % public_name,
        "",
        "## Run information",
        "",
        "| Item | Value |",
        "|---|---|",
        "| Run time (UTC) | %s |" % run_time.strftime("%Y-%m-%d %H:%M:%S"),
        "| Run time (local) | %s |" % local_time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "| Base URL | %s |" % BASE_URL,
        "| Operating system | %s |" % platform.platform(),
        "| Python | %s (%s) |" % (platform.python_version(), platform.python_implementation()),
        "| requests | %s |" % requests.__version__,
        "| Timeout per request | %s seconds |" % TIMEOUT_SECONDS,
        "| Requests sent | %d |" % len(records),
        "| Status codes | %s |" % count_statuses(records),
        "",
        "## Changes since the previous run",
        "",
    ]
    if previous_name is None:
        lines.append("No earlier run to compare with. This is the baseline.")
    elif not changes:
        lines.append("No change in status codes or body structure compared with `%s`." % previous_name)
    else:
        lines.append("Compared with `%s`:" % previous_name)
        lines.append("")
        lines += ["- %s" % change for change in changes]

    lines += ["", "## Details", ""]
    for r in records:
        lines += ["### #%d %s %s" % (r["number"], r["method"], r["path"]), ""]
        lines.append("- Question: %s" % r["question"])
        lines.append("- Sent body: %s" % ("none" if r["sent"] is None else "`%s`" % json.dumps(r["sent"])))
        lines.append("- Status: %s" % r["status"])
        if r["seconds"] is not None:
            lines.append("- Response time: %.3f s" % r["seconds"])
        if r["error"]:
            lines += ["- Error type: %s" % r["summary"], "", "Full error message:", "", "```", r["error"], "```"]
        if r["headers"]:
            lines += ["", "Response headers:", "", "```"]
            lines += ["%s: %s" % (name, value) for name, value in r["headers"].items()]
            lines.append("```")
        if r["body"]:
            lines += ["", "Response body:", "", "```", r["body"], "```"]
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def update_local_index(run_time, records, local_name, changes, previous_name):
    """Add one row for this run to the local index."""
    if not LOCAL_INDEX_FILE.exists():
        header = [
            "# API observation index (full local records)",
            "",
            "LOCAL USE ONLY. Excluded from version control by .gitignore.",
            "",
            "| Run time (UTC) | Run time (local) | Status codes | Errors | Changes vs previous run | Full record |",
            "|---|---|---|---|---|---|",
        ]
        LOCAL_INDEX_FILE.write_text("\n".join(header) + "\n", encoding="utf-8")

    errors = sum(1 for r in records if r["status"] == "ERROR")
    if previous_name is None:
        change_text = "baseline"
    elif not changes:
        change_text = "none"
    else:
        change_text = "%d change(s)" % len(changes)
    row = "| %s | %s | %s | %d | %s | [%s](%s) |\n" % (
        run_time.strftime("%Y-%m-%d %H:%M:%S"),
        run_time.astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        count_statuses(records), errors, change_text, local_name, local_name,
    )
    with open(LOCAL_INDEX_FILE, "a", encoding="utf-8") as handle:
        handle.write(row)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone.utc)
    stamp = run_time.strftime("%Y%m%d_%H%M%S")

    # Read the previous run before writing new files.
    previous_name, previous_records = load_previous_run()

    full_records = run_probes()
    public_records = [to_public_record(record) for record in full_records]
    changes = find_changes(previous_records, public_records) if previous_records else []

    # Public record: safe to commit.
    public_name = "observed_%s.md" % stamp
    write_detail_file(OUTPUT_DIR / public_name, run_time, public_records, previous_name, changes)
    write_data_file(OUTPUT_DIR / ("observed_%s.json" % stamp), run_time, public_records)
    update_index(run_time, public_records, public_name, previous_name, changes)

    # Full local record: for troubleshooting, never committed.
    local_name = "observed_%s_full.md" % stamp
    write_local_detail_file(LOCAL_DIR / local_name, run_time, full_records, public_name, previous_name, changes)
    update_local_index(run_time, full_records, local_name, changes, previous_name)

    print("")
    print("Status codes: %s" % count_statuses(full_records))
    if previous_name is None:
        print("Changes: none to report (first run, saved as baseline)")
    else:
        print("Changes since previous run: %d" % len(changes))
        for change in changes:
            print("  - %s" % change)
    print("Public record: docs/observations/%s" % public_name)
    print("Local record:  observations_local/%s  (not committed)" % local_name)


if __name__ == "__main__":
    main()
