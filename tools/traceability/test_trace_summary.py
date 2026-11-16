"""Unit tests for trace_summary.py.

Run from the project root:
    python -m unittest discover -s tools/traceability -p "test_*.py"
"""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import trace_summary

PLAN_ROWS = {
    "POS-01": "| POS-01 | title | P0 | GET /posts | 200 | none | #1 |",
    "POS-02": "| POS-02 | title | P0 | GET /posts/1 | 200 | id=1 | #2 |",
    "BND-01": "| BND-01 | title | P1 | GET /posts/1 | 200 | id=1 | #2 |",
    "BND-02": "| BND-02 | title | P1 | GET /posts/100 | 200 | id=100 | #9 |",
    "NEG-01": "| NEG-01 | title | P1 | GET /x | 404 | none | #14 |",
    "ERR-01": "| ERR-01 | title | P1 | GET /posts | timeout | none | n/a |",
    "REP-01": "| REP-01 | title | P1 | GET /posts/1 x3 | same | id=1 | #2 |",
}

TEST_SOURCE = '''
import pytest


def test_a():
    """POS-01 (P0): first."""


def test_b():
    """POS-02 (P0): second."""


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("1", id="BND-01-lowest"),
        pytest.param("100", id="BND-02-highest"),
    ],
)
def test_c(value):
    """Boundary ids."""


def test_d():
    """NEG-01 (P1): third."""


def test_e():
    """ERR-01 (P1): fourth."""


def test_f():
    """REP-01 (P1): fifth."""


def test_smoke():
    """Smoke check (related to POS-02 in the plan)."""
'''


class Workspace(unittest.TestCase):
    def setUp(self):
        # The summary goes to a file only when this variable is set.
        self.saved = os.environ.pop("GITHUB_STEP_SUMMARY", None)
        self.root = Path(tempfile.mkdtemp())
        self.tests_dir = self.root / "tests"
        self.tests_dir.mkdir()
        self.plan = self.root / "test_plan.md"

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)
        if self.saved is not None:
            os.environ["GITHUB_STEP_SUMMARY"] = self.saved

    def write_plan(self, ids):
        lines = ["# Plan", "", "| ID | Title |", "|---|---|"]
        lines += [PLAN_ROWS[i] for i in ids]
        self.plan.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_tests(self, source=TEST_SOURCE):
        (self.tests_dir / "test_sample.py").write_text(source, encoding="utf-8")

    def run_main(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        argv = ["--plan", str(self.plan), "--tests", str(self.tests_dir)] + list(extra)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = trace_summary.main(argv)
        return code, out.getvalue(), err.getvalue()


class ReadingIds(Workspace):
    def test_plan_ids_are_read_from_table_rows_only(self):
        self.plan.write_text(
            "POS-09 mentioned in prose\n| POS-01 | a |\n| Title | POS-02 |\n", encoding="utf-8")
        self.assertEqual(trace_summary.read_plan_ids(str(self.plan)), ["POS-01"])

    def test_docstring_param_and_range_ids_are_read(self):
        self.write_tests(
            'import pytest\n\n'
            '@pytest.mark.parametrize("x", [pytest.param(1, id="BND-03-low")])\n'
            'def test_one(x):\n    """BND-03 to BND-05: range."""\n\n'
            'def test_two():\n    """Smoke (related to POS-02)."""\n')
        function_ids, untagged = trace_summary.read_test_ids(str(self.tests_dir))
        self.assertEqual(function_ids[("test_sample", "test_one")], {"BND-03", "BND-04", "BND-05"})
        self.assertEqual(untagged, ["test_sample::test_two"])


class Comparison(Workspace):
    def test_matching_sides_pass_and_summary_is_printed(self):
        self.write_plan(list(PLAN_ROWS))
        self.write_tests()
        code, out, err = self.run_main()
        self.assertEqual(code, 0, err)
        self.assertIn("Traceability: **OK**", out)
        self.assertIn("| **Total** | **7** | **7** |", out)
        self.assertIn("Tests without a Test ID: 1", out)

    def test_id_missing_from_tests_fails(self):
        self.write_plan(list(PLAN_ROWS))
        self.write_tests(TEST_SOURCE.replace("REP-01 (P1): fifth.", "Fifth."))
        code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("REP-01 is in the test plan but no test covers it.", err)

    def test_id_missing_from_plan_fails(self):
        ids = [i for i in PLAN_ROWS if i != "NEG-01"]
        self.write_plan(ids)
        self.write_tests()
        code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("NEG-01 is covered by a test but is not in the test plan.", err)

    def test_gap_in_numbering_fails(self):
        self.write_plan(["POS-01", "POS-02", "BND-01", "BND-02", "NEG-01", "ERR-01", "REP-01"])
        self.write_tests(TEST_SOURCE.replace("POS-02 (P0): second.", "POS-03 (P0): second."))
        code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("skips POS-02", err)

    def test_missing_category_fails(self):
        ids = [i for i in PLAN_ROWS if not i.startswith("REP")]
        self.write_plan(ids)
        self.write_tests(TEST_SOURCE.replace("REP-01 (P1): fifth.", "Fifth."))
        code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("no Test ID in category Repeat (REP)", err)

    def test_empty_plan_and_tests_fail_instead_of_passing(self):
        self.plan.write_text("# nothing here\n", encoding="utf-8")
        self.write_tests("def test_x():\n    pass\n")
        code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("No Test ID was found in the test plan", err)
        self.assertIn("No Test ID was found in the tests", err)

    def test_duplicate_plan_id_fails(self):
        self.write_plan(list(PLAN_ROWS) + ["POS-01"])
        self.write_tests()
        code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("POS-01 appears more than once", err)


class Results(Workspace):
    JUNIT = (
        '<?xml version="1.0"?><testsuites><testsuite>'
        '<testcase classname="tests.test_sample" name="test_a"/>'
        '<testcase classname="tests.test_sample" name="test_b"><failure message="x"/></testcase>'
        '<testcase classname="tests.test_sample" name="test_c[BND-01-lowest]"/>'
        '<testcase classname="tests.test_sample" name="test_c[BND-02-highest]"><skipped/></testcase>'
        '<testcase classname="tests.test_sample" name="test_d"/>'
        '<testcase classname="tests.test_sample" name="test_e"/>'
        '<testcase classname="tests.test_sample" name="test_f"/>'
        '<testcase classname="tests.test_sample" name="test_smoke"/>'
        '</testsuite></testsuites>'
    )

    def test_results_are_counted_per_test_id(self):
        self.write_plan(list(PLAN_ROWS))
        self.write_tests()
        junit = self.root / "junit.xml"
        junit.write_text(self.JUNIT, encoding="utf-8")
        function_ids, _ = trace_summary.read_test_ids(str(self.tests_dir))
        status, untagged = trace_summary.read_junit(str(junit), function_ids)
        self.assertEqual(status["POS-01"], "passed")
        self.assertEqual(status["POS-02"], "failed")
        self.assertEqual(status["BND-01"], "passed")
        self.assertEqual(status["BND-02"], "skipped")
        self.assertEqual(list(untagged), ["test_sample::test_smoke"])

    def test_summary_counts_passed_and_not_passed(self):
        self.write_plan(list(PLAN_ROWS))
        self.write_tests()
        junit = self.root / "junit.xml"
        junit.write_text(self.JUNIT, encoding="utf-8")
        code, out, err = self.run_main("--junit", str(junit), "--label", "Python 3.11")
        self.assertEqual(code, 0, err)
        self.assertIn("### Traceability and results (Python 3.11)", out)
        self.assertIn("| Positive (POS) | 2 | 2 | 1 | 1 |", out)
        self.assertIn("| Boundary (BND) | 2 | 2 | 1 | 1 |", out)
        self.assertIn("| **Total** | **7** | **7** | **5** | **2** |", out)

    def test_summary_is_appended_to_the_job_summary_file(self):
        self.write_plan(list(PLAN_ROWS))
        self.write_tests()
        target = self.root / "summary.md"
        os.environ["GITHUB_STEP_SUMMARY"] = str(target)
        try:
            code, out, err = self.run_main()
        finally:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        self.assertEqual(code, 0, err)
        self.assertIn("Traceability: **OK**", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
