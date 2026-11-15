#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lesson_counter.py 雙向陷阱測試(攔得住 + 不誤判)
執行:python3 test_lesson_counter.py
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.environ.get("LESSON_COUNTER_PY", os.path.join(HERE, "lesson_counter.py"))

VERIFY_STUB = u"def check_tbl_bracket(text, result):\n    return True\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="lc_")
        self.w("verify.py", VERIFY_STUB)
        self.w("lessons.md", u"# 教訓\n")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def w(self, rel, text):
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return p

    def day(self, date, *lines):
        self.w("journal/{0}.md".format(date), u"## {0} — 測試\n\n".format(date) + u"".join(u"- " + l + u"\n" for l in lines))

    def run_tool(self, *extra, **kw):
        args = [sys.executable, "-I", TOOL, "--journal", os.path.join(self.d, "journal"),
                "--lessons", os.path.join(self.d, "lessons.md"),
                "--verify-py", os.path.join(self.d, "verify.py"), "--root", self.d] + list(extra)
        env = dict(os.environ)
        env.pop("GITHUB_STEP_SUMMARY", None)
        env.update(kw.get("env", {}))
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", env=env)
        return r.returncode, r.stdout + r.stderr


class Counting(Base):
    def test_l01_single_occurrence_passes(self):
        self.day("2026-11-01", u"tbl 括號寫錯 [錯誤:tbl-bracket]")
        code, out = self.run_tool()
        self.assertEqual(code, 0, out)

    def test_l02_second_occurrence_becomes_candidate(self):
        self.day("2026-11-01", u"tbl 括號寫錯 [錯誤:tbl-bracket]")
        self.day("2026-11-08", u"又是 tbl 括號 [錯誤:tbl-bracket]")
        code, out = self.run_tool()
        self.assertEqual(code, 1, out)
        self.assertIn("晉升候選", out)
        self.assertIn("2026-11-01、2026-11-08", out)

    def test_l03_promoted_before_closes(self):
        self.day("2026-11-01", u"[錯誤:tbl-bracket]")
        self.day("2026-11-08", u"[錯誤:tbl-bracket]")
        self.w("lessons.md", u"- L-20261109-01 類別:tbl-bracket 檢查:check_tbl_bracket — 括號\n")
        code, out = self.run_tool()
        self.assertEqual(code, 0, out)

    def test_l04_relapse_after_promotion(self):
        """晉升後又出現:代表檢查沒擋住"""
        self.day("2026-11-01", u"[錯誤:tbl-bracket]")
        self.day("2026-11-12", u"[錯誤:tbl-bracket]")
        self.w("lessons.md", u"- L-20261109-01 類別:tbl-bracket 檢查:check_tbl_bracket\n")
        code, out = self.run_tool()
        self.assertEqual(code, 1, out)
        self.assertIn("復發", out)

    def test_l05_false_closure(self):
        """宣稱有檢查、實際找不到函式"""
        self.day("2026-11-01", u"[錯誤:sql-null-compare]")
        self.w("lessons.md", u"- L-20261114-01 類別:sql-null-compare 檢查:check_sql_null\n")
        code, out = self.run_tool()
        self.assertEqual(code, 1, out)
        self.assertIn("假關閉", out)

    def test_l06_file_func_check(self):
        self.day("2026-11-01", u"[錯誤:sql-null-compare]")
        self.day("2026-11-02", u"[錯誤:sql-null-compare]")
        self.w("lessons.md", u"- 2026-11-03 類別:sql-null-compare 檢查:tests/test_ingest.py::test_null_batch\n")
        self.w("tests/test_ingest.py", u"def test_other():\n    pass\n")
        self.assertEqual(self.run_tool()[0], 1)
        self.w("tests/test_ingest.py", u"def test_null_batch():\n    pass\n")
        code, out = self.run_tool()
        self.assertEqual(code, 0, out)

    def test_l13_recorded_without_check_is_still_candidate(self):
        self.day("2026-11-01", u"[錯誤:wrong-root-cause]")
        self.day("2026-11-02", u"[錯誤:wrong-root-cause]")
        self.w("lessons.md", u"- L-20261103-01 類別:wrong-root-cause — 只寫了文字教訓\n")
        code, out = self.run_tool()
        self.assertEqual(code, 1, out)
        self.assertIn("有記錄但沒有檢查", out)


class Parsing(Base):
    def test_l07_similar_tags_warn_only(self):
        self.day("2026-11-01", u"[錯誤:tbl-bracket]")
        self.day("2026-11-02", u"[錯誤:tbl-brackets]")
        code, out = self.run_tool()
        self.assertEqual(code, 0, out)
        self.assertIn("疑似同類", out)

    def test_l08_same_tag_twice_in_one_line_counts_once(self):
        self.day("2026-11-01", u"[錯誤:tbl-bracket] 同一件事 [錯誤:tbl-bracket]")
        self.assertEqual(self.run_tool()[0], 0)

    def test_l09_fullwidth_marks(self):
        self.day("2026-11-01", u"［錯誤：tbl-bracket］")
        self.day("2026-11-02", u"[錯誤：tbl-bracket]")
        code, out = self.run_tool()
        self.assertEqual(code, 1, out)

    def test_l10_missing_journal(self):
        shutil.rmtree(os.path.join(self.d, "journal"), ignore_errors=True)
        self.assertEqual(self.run_tool()[0], 2)

    def test_l11_warn_only(self):
        self.day("2026-11-01", u"[錯誤:tbl-bracket]")
        self.day("2026-11-02", u"[錯誤:tbl-bracket]")
        code, out = self.run_tool("--warn-only")
        self.assertEqual(code, 0, out)
        self.assertIn("晉升候選", out)

    def test_l12_date_from_filename_when_no_header(self):
        self.w("journal/2026-11-01.md", u"- [錯誤:tbl-bracket]\n")
        self.w("journal/2026-11-12.md", u"- [錯誤:tbl-bracket]\n")
        self.w("lessons.md", u"- L-20261109-01 類別:tbl-bracket 檢查:check_tbl_bracket\n")
        code, out = self.run_tool()
        self.assertEqual(code, 1, out)
        self.assertIn("復發", out)

    def test_l14_multiple_headers_in_one_file(self):
        self.w("journal/all.md", u"## 2026-11-01 — a\n- [錯誤:tbl-bracket]\n\n## 2026-11-12 — b\n- [錯誤:tbl-bracket]\n")
        self.w("lessons.md", u"- L-20261109-01 類別:tbl-bracket 檢查:check_tbl_bracket\n")
        code, out = self.run_tool()
        self.assertEqual(code, 1, out)
        self.assertIn("2026-11-12", out)

    def test_l15_list_and_summary(self):
        self.day("2026-11-01", u"[錯誤:tbl-bracket]")
        s = os.path.join(self.d, "summary.md")
        code, out = self.run_tool("--list", env={"GITHUB_STEP_SUMMARY": s})
        self.assertEqual(code, 0, out)
        with io.open(s, encoding="utf-8") as f:
            self.assertIn("| `tbl-bracket` | 1 | 2026-11-01 |", f.read())

    def test_l16_untagged_text_is_ignored(self):
        self.day("2026-11-01", u"提到錯誤:tbl-bracket 但沒有括號", u"[錯誤:Bad_Tag]")
        code, out = self.run_tool("--list")
        self.assertEqual(code, 0, out)
        self.assertIn("尚無任何", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
