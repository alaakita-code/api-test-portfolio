"""Compare Test IDs in the test plan with Test IDs in the tests and print a summary.

Test IDs have the form POS-01, BND-03, NEG-02, ERR-01, REP-02. They are read from:
  - the test plan: table rows that start with a Test ID
  - the tests: the first words of a test function's docstring ("POS-01 (P0): ...",
    or a range such as "BND-03 to BND-06") and pytest.param(..., id="BND-03-...")

The script exits with code 1 when the two sides do not match, so that a case
that exists in only one place is noticed. It checks:
  - the plan or the tests contain no Test ID at all
  - a category has no Test ID
  - the numbers of a category have a gap (POS-01, POS-03 without POS-02)
  - a Test ID appears in the plan but not in the tests, or the reverse
  - a Test ID appears more than once in the plan

If a JUnit XML file is given, the summary also shows how many cases passed.
When the environment variable GITHUB_STEP_SUMMARY is set, the summary is
appended to that file; otherwise it is printed.

Usage (from the project root):
    python tools/traceability/trace_summary.py --junit reports/junit.xml
"""

import argparse
import ast
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

CATEGORIES = [
    ("POS", "Positive"),
    ("BND", "Boundary"),
    ("NEG", "Negative"),
    ("ERR", "Error handling"),
    ("REP", "Repeat"),
]
PREFIXES = [prefix for prefix, _ in CATEGORIES]
ID_PATTERN = "(?:{})-\\d{{2}}".format("|".join(PREFIXES))

PLAN_ROW = re.compile(r"^\|\s*(" + ID_PATTERN + r")\s*\|")
DOC_HEAD = re.compile(r"^\s*(" + ID_PATTERN + r")(?:\s+to\s+(" + ID_PATTERN + r"))?")
PARAM_ID = re.compile(r"^(" + ID_PATTERN + r")-")
ANY_ID = re.compile(ID_PATTERN)


def split_id(test_id):
    prefix, number = test_id.split("-")
    return prefix, int(number)


def expand_range(first, last):
    """Return the IDs from first to last, e.g. BND-03 to BND-06 -> four IDs."""
    first_prefix, first_number = split_id(first)
    last_prefix, last_number = split_id(last)
    if first_prefix != last_prefix or last_number < first_number:
        return [first, last]
    return ["{}-{:02d}".format(first_prefix, n) for n in range(first_number, last_number + 1)]


def read_plan_ids(plan_path):
    """Return every Test ID that starts a table row in the test plan, in order."""
    ids = []
    with open(plan_path, encoding="utf-8") as handle:
        for line in handle:
            match = PLAN_ROW.match(line)
            if match:
                ids.append(match.group(1))
    return ids


def read_test_ids(tests_dir):
    """Scan test_*.py files.

    Returns (function_ids, untagged):
      function_ids maps (module name, function name) to the set of Test IDs it covers
      untagged is the list of test functions that declare no Test ID
    """
    function_ids = {}
    untagged = []
    for path in sorted(Path(tests_dir).glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            ids = set()
            doc = ast.get_docstring(node) or ""
            head = DOC_HEAD.match(doc.splitlines()[0]) if doc else None
            if head:
                if head.group(2):
                    ids.update(expand_range(head.group(1), head.group(2)))
                else:
                    ids.add(head.group(1))
            for decorator in node.decorator_list:
                for sub in ast.walk(decorator):
                    if (
                        isinstance(sub, ast.keyword)
                        and sub.arg == "id"
                        and isinstance(sub.value, ast.Constant)
                        and isinstance(sub.value.value, str)
                    ):
                        param = PARAM_ID.match(sub.value.value)
                        if param:
                            ids.add(param.group(1))
            key = (path.stem, node.name)
            if ids:
                function_ids[key] = ids
            else:
                untagged.append("{}::{}".format(path.stem, node.name))
    return function_ids, untagged


def read_junit(junit_path, function_ids):
    """Return ({Test ID: 'passed' | 'failed' | 'skipped'}, [untagged results])."""
    status = {}
    untagged = {}
    root = ET.parse(junit_path).getroot()
    for case in root.iter("testcase"):
        module = (case.get("classname") or "").split(".")[-1]
        name = case.get("name") or ""
        function = name.split("[")[0]
        if case.find("failure") is not None or case.find("error") is not None:
            result = "failed"
        elif case.find("skipped") is not None:
            result = "skipped"
        else:
            result = "passed"
        ids = function_ids.get((module, function), set())
        if "[" in name:
            param = ANY_ID.match(name[name.index("[") + 1:])
            if param:
                ids = {param.group(0)}
        if not ids:
            untagged["{}::{}".format(module, name)] = result
            continue
        for test_id in ids:
            previous = status.get(test_id)
            if previous == "failed" or result == "failed":
                status[test_id] = "failed"
            elif previous == "skipped" or result == "skipped":
                status[test_id] = "skipped"
            else:
                status[test_id] = "passed"
    return status, untagged


def numbering_gaps(ids):
    """Return the missing IDs between 01 and the highest number of each category."""
    gaps = []
    for prefix in PREFIXES:
        numbers = sorted({split_id(i)[1] for i in ids if i.startswith(prefix + "-")})
        if not numbers:
            continue
        for number in range(1, numbers[-1] + 1):
            if number not in numbers:
                gaps.append("{}-{:02d}".format(prefix, number))
    return gaps


def find_problems(plan_list, test_ids):
    """Return a list of readable problems; an empty list means the two sides match."""
    problems = []
    plan_ids = set(plan_list)
    if not plan_ids:
        problems.append("No Test ID was found in the test plan (check the file path and the table format).")
    if not test_ids:
        problems.append("No Test ID was found in the tests (check the folder and the docstring format).")

    for source, ids in (("test plan", plan_ids), ("tests", test_ids)):
        if not ids:
            continue
        for prefix, label in CATEGORIES:
            if not any(i.startswith(prefix + "-") for i in ids):
                problems.append("The {} has no Test ID in category {} ({}).".format(source, label, prefix))
        for gap in numbering_gaps(ids):
            problems.append("The {} skips {} (numbers of a category must be continuous).".format(source, gap))

    for test_id in sorted(plan_ids - test_ids):
        problems.append("{} is in the test plan but no test covers it.".format(test_id))
    for test_id in sorted(test_ids - plan_ids):
        problems.append("{} is covered by a test but is not in the test plan.".format(test_id))
    seen = set()
    for test_id in plan_list:
        if test_id in seen:
            problems.append("{} appears more than once in the test plan.".format(test_id))
        seen.add(test_id)
    return problems


def build_summary(label, plan_list, test_ids, untagged, junit_status, problems):
    """Return the summary as Markdown text."""
    plan_ids = set(plan_list)
    title = "Traceability and results" + (" ({})".format(label) if label else "")
    lines = ["### " + title, ""]
    lines.append("| Category | Planned | Implemented | Passed | Not passed |")
    lines.append("|---|---:|---:|---:|---:|")
    totals = [0, 0, 0, 0]
    for prefix, name in CATEGORIES:
        planned = {i for i in plan_ids if i.startswith(prefix + "-")}
        implemented = planned & test_ids
        if junit_status is None:
            passed = not_passed = None
        else:
            passed = len({i for i in implemented if junit_status.get(i) == "passed"})
            not_passed = len(implemented) - passed
        row = [len(planned), len(implemented), passed, not_passed]
        for index, value in enumerate(row):
            if value is not None:
                totals[index] += value
        lines.append("| {} ({}) | {} | {} | {} | {} |".format(
            name, prefix, row[0], row[1],
            "-" if passed is None else passed,
            "-" if not_passed is None else not_passed))
    if junit_status is None:
        lines.append("| **Total** | **{}** | **{}** | - | - |".format(totals[0], totals[1]))
    else:
        lines.append("| **Total** | **{}** | **{}** | **{}** | **{}** |".format(*totals))
    lines.append("")
    if untagged:
        lines.append("Tests without a Test ID: {} ({})".format(len(untagged), ", ".join(untagged)))
        lines.append("")
    if problems:
        lines.append("Traceability: **{} problem(s)**".format(len(problems)))
        lines.extend("- " + problem for problem in problems)
    else:
        lines.append("Traceability: **OK** - every Test ID in the test plan has a test, and every tagged test is in the plan.")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare Test IDs in the test plan with the tests.")
    parser.add_argument("--plan", default="docs/test_plan.md", help="path of the test plan")
    parser.add_argument("--tests", default="tests", help="folder that holds the test files")
    parser.add_argument("--junit", default=None, help="JUnit XML file written by pytest --junitxml")
    parser.add_argument("--label", default="", help="text added to the summary title, e.g. Python 3.11")
    args = parser.parse_args(argv)

    plan_list = read_plan_ids(args.plan)
    function_ids, untagged = read_test_ids(args.tests)
    test_ids = set().union(*function_ids.values()) if function_ids else set()
    problems = find_problems(plan_list, test_ids)

    junit_status = None
    if args.junit and Path(args.junit).exists():
        junit_status, _ = read_junit(args.junit, function_ids)

    summary = build_summary(args.label, plan_list, test_ids, untagged, junit_status, problems)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(summary + "\n")
    print(summary)
    for problem in problems:
        print("ERROR: " + problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
