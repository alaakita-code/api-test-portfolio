#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gate.py 雙向陷阱測試:在暫存 git repo 模擬 PR、推送、手動執行等情境。
執行:python3 test_gate.py

本檔測的是「擋關邏輯」,用替身驗收器取代 verify.py(含 => 就失敗),
所以不論你本機 verify.py 是哪一版、加了哪些檢查,這些測試結果都一致。
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "gate.py")

OLD_HTML = u"""﻿<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div id="app"><div class="tab">內容</div></div>
<script>
function svgRoad(){ return '<svg></svg>'; }
function renderLab(){ var x = 1; return x; }
</script></body></html>
"""
NEW_HTML = OLD_HTML.replace(
    "function renderLab()", "function renderArch(){ return svgRoad(); }\nfunction renderLab()")
ES6_HTML = NEW_HTML.replace("function renderArch(){ return svgRoad(); }",
                            "var renderArch = () => svgRoad();")

PY = sys.executable
STUB_VERIFY = u"""import sys, io
t = io.open(sys.argv[1], encoding="utf-8-sig").read()
print("stub verify")
sys.exit(1 if "=>" in t else 0)
"""
GOOD_CFG = u"verify  dist/*.html\ntest    \"{0}\" -c \"print('ok')\"\n".format(PY)
EXPECT = u"+ dist/index.html :: renderArch\n= dist/index.html :: function svgRoad(\n"


class GateCase(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="gate_")
        self.w("dist/index.html", OLD_HTML)
        self.w(".alaakita/gate.txt", GOOD_CFG)
        self.w(".alaakita/expect.txt", u"= dist/index.html :: function svgRoad(\n")
        self.git("init", "-q")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.stub = os.path.join(tempfile.mkdtemp(prefix="stub_"), "verify_stub.py")
        with io.open(self.stub, "w", encoding="utf-8") as f:
            f.write(STUB_VERIFY)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)
        shutil.rmtree(os.path.dirname(self.stub), ignore_errors=True)

    def w(self, rel, text):
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def git(self, *a):
        return subprocess.run(["git", "-C", self.d] + list(a), capture_output=True,
                              text=True, check=True).stdout

    def commit(self, msg):
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)

    def gate(self, base=None, env=None):
        args = [PY, "-I", GATE, "--root", self.d, "--verify-py", self.stub]
        if base is not None:
            args += ["--base", base]
        e = dict(os.environ)
        e.pop("GITHUB_STEP_SUMMARY", None)
        e.update(env or {})
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", env=e)
        return r.returncode, r.stdout + r.stderr

    # ---- 攔得住 ----
    def test_g01_clean_pr_passes(self):
        self.w("dist/index.html", NEW_HTML)
        self.w(".alaakita/expect.txt", EXPECT)
        self.commit("add arch")
        code, out = self.gate(self.base)
        self.assertEqual(code, 0, out)
        self.assertIn("全綠,可以合併", out)

    def test_g02_stale_expect_blocks(self):
        """忘了更新預期檔:舊規則無法證明這次改動"""
        self.w("dist/index.html", NEW_HTML)
        self.w(".alaakita/expect.txt", EXPECT)
        self.commit("pr1")
        base2 = self.git("rev-parse", "HEAD").strip()
        self.w("dist/index.html", NEW_HTML.replace("內容", "內容二"))
        self.commit("pr2 without new expect")
        code, out = self.gate(base2)
        self.assertEqual(code, 1, out)

    def test_g03_verify_failure_blocks(self):
        self.w("dist/index.html", ES6_HTML)
        self.w(".alaakita/expect.txt", EXPECT)
        self.commit("es6")
        code, out = self.gate(self.base)
        self.assertEqual(code, 1, out)
        self.assertIn("verify dist/index.html 的輸出", out)

    def test_g04_verify_pattern_matches_nothing(self):
        self.w(".alaakita/gate.txt", GOOD_CFG.replace("dist/*.html", "build/*.html"))
        code, out = self.gate()
        self.assertEqual(code, 1, out)
        self.assertIn("樣式找不到任何檔案", out)

    def test_g05_no_checks_is_config_error(self):
        self.w(".alaakita/gate.txt", u"# 空的\nexpect .alaakita/expect.txt\n")
        code, out = self.gate()
        self.assertEqual(code, 2, out)

    def test_g07_base_without_expect_blocks(self):
        os.remove(os.path.join(self.d, ".alaakita/expect.txt"))
        self.w("dist/index.html", NEW_HTML)
        self.commit("no expect")
        code, out = self.gate(self.base)
        self.assertEqual(code, 1, out)
        self.assertIn("沒有預期檔", out)

    def test_g08_failing_test_command_blocks(self):
        self.w(".alaakita/gate.txt", u"verify  dist/*.html\ntest    \"{0}\" -c \"import sys; sys.exit(3)\"\n".format(PY))
        code, out = self.gate()
        self.assertEqual(code, 1, out)
        self.assertIn("exit 3", out)

    def test_g09_only_expect_changed_blocks(self):
        """只改預期檔、內容沒動:不能算有改動"""
        self.w(".alaakita/expect.txt", u"= dist/index.html :: function svgRoad(\n= dist/index.html :: renderLab\n")
        self.commit("expect only")
        code, out = self.gate(self.base)
        self.assertEqual(code, 1, out)

    def test_g12_unknown_base_blocks(self):
        code, out = self.gate("1234567890abcdef1234567890abcdef12345678")
        self.assertEqual(code, 1, out)
        self.assertIn("找不到比較基準", out)

    def test_g13_bad_config_line(self):
        self.w(".alaakita/gate.txt", u"verfy dist/*.html\n")
        self.assertEqual(self.gate()[0], 2)

    # ---- 不誤判 ----
    def test_g06_no_base_skips_path_only(self):
        code, out = self.gate("")
        self.assertEqual(code, 0, out)
        self.assertIn("略過", out)

    def test_g10_zero_sha_is_treated_as_no_base(self):
        code, out = self.gate("0" * 40)
        self.assertEqual(code, 0, out)
        self.assertIn("略過", out)

    def test_g11_writes_step_summary(self):
        s = os.path.join(self.d, "summary.md")
        code, out = self.gate("", env={"GITHUB_STEP_SUMMARY": s})
        self.assertEqual(code, 0, out)
        with io.open(s, encoding="utf-8") as f:
            self.assertIn("| verify | `dist/index.html` | ✅ 通過 |", f.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
