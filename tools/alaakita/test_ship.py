#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ship.py 雙向陷阱測試:暫存 bare repo 當 GitHub 遠端、假 gh 模擬 PR 與檢查結果。
執行:python3 test_ship.py
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHIP = os.environ.get("SHIP_PY", os.path.join(HERE, "ship.py"))
PY = sys.executable

# 假 gh:狀態存在 FAKE_GH_STATE 指向的 JSON 檔
FAKE_GH = u'''import json, os, sys
p = os.environ["FAKE_GH_STATE"]
s = json.load(open(p, encoding="utf-8"))
a = sys.argv[1:]
s.setdefault("calls", []).append(a)
def save():
    json.dump(s, open(p, "w", encoding="utf-8"))
if a[:2] == ["pr", "view"]:
    save()
    if not s.get("pr"):
        sys.stderr.write("no pull requests found\\n"); sys.exit(1)
    print(json.dumps(s["pr"])); sys.exit(0)
if a[:2] == ["pr", "create"]:
    s["pr"] = {"url": "https://example.test/pull/1", "state": "OPEN"}
    s["created"] = s.get("created", 0) + 1
    save(); print(s["pr"]["url"]); sys.exit(0)
if a[:2] == ["pr", "checks"]:
    seq = s.get("checks_seq", [])
    i = min(s.get("checks_i", 0), len(seq) - 1) if seq else -1
    s["checks_i"] = s.get("checks_i", 0) + 1
    save()
    if i < 0 or seq[i] is None:
        sys.stderr.write("no checks reported on the branch\\n"); sys.exit(1)
    print(json.dumps(seq[i])); sys.exit(0)
save(); sys.stderr.write("unknown " + " ".join(a)); sys.exit(3)
'''

GATE_CFG = u"test    \"{0}\" -c \"print('ok')\"\n".format(PY)
PASS3 = [{"name": "gate", "bucket": "pass", "link": "l1"},
         {"name": "Python 3.11", "bucket": "pass", "link": "l2"},
         {"name": "Python 3.13", "bucket": "pass", "link": "l3"}]


class ShipCase(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="ship_")
        self.remote = os.path.join(self.d, "remote.git")
        self.repo = os.path.join(self.d, "repo")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.remote], check=True)
        os.makedirs(self.repo)
        self.g("init", "-q", "-b", "main")
        self.g("config", "user.email", "t@t")
        self.g("config", "user.name", "t")
        shutil.copytree(HERE, os.path.join(self.repo, "tools", "alaakita"),
                        ignore=shutil.ignore_patterns("__pycache__", "test_*.py"))
        if os.path.abspath(SHIP) != os.path.join(HERE, "ship.py"):
            shutil.copy(SHIP, os.path.join(self.repo, "tools", "alaakita", "ship.py"))
        self.w(".alaakita/gate.txt", GATE_CFG)
        self.w(".alaakita/expect.txt", u"# base\n")
        self.w("README.md", u"# Demo\n\nline one\n")
        self.g("add", "-A")
        self.g("commit", "-qm", "base")
        self.g("remote", "add", "origin", self.remote)
        self.g("push", "-q", "-u", "origin", "main")
        self.state = os.path.join(self.d, "gh_state.json")
        self.fake = os.path.join(self.d, "fake_gh.py")
        with io.open(self.fake, "w", encoding="utf-8") as f:
            f.write(FAKE_GH)
        self.set_gh({"checks_seq": [PASS3]})

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def g(self, *a):
        return subprocess.run(["git", "-C", self.repo] + list(a), capture_output=True,
                              text=True, check=True).stdout

    def w(self, rel, text):
        p = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def set_gh(self, st):
        with io.open(self.state, "w", encoding="utf-8") as f:
            json.dump(st, f)

    def gh_state(self):
        with io.open(self.state, encoding="utf-8") as f:
            return json.load(f)

    def ship(self, *a):
        env = dict(os.environ, SHIP_GH=self.fake, FAKE_GH_STATE=self.state,
                   SHIP_POLL_SECONDS="0", SHIP_TIMEOUT_SECONDS="0.5")
        env.pop("GITHUB_STEP_SUMMARY", None)
        r = subprocess.run([PY, "-I", os.path.join(self.repo, "tools", "alaakita", "ship.py")] + list(a),
                           cwd=self.repo, capture_output=True, text=True, encoding="utf-8", env=env)
        return r.returncode, r.stdout + r.stderr

    def remote_has(self, branch):
        r = subprocess.run(["git", "--git-dir", self.remote, "rev-parse", "--verify", "refs/heads/" + branch],
                           capture_output=True)
        return r.returncode == 0

    def good_change(self):
        self.w(".alaakita/expect.txt", u"+ README.md :: line two\n= README.md :: line one\n")
        self.w("README.md", u"# Demo\n\nline one\nline two\n")


class Start(ShipCase):
    def test_s01_dirty_tree_refused(self):
        self.w("README.md", u"dirty\n")
        code, out = self.ship("start", "docs/x")
        self.assertEqual(code, 1, out)
        self.assertIn("尚未 commit", out)
        self.assertEqual(self.g("branch", "--show-current").strip(), "main")

    def test_s02_start_creates_branch_and_template(self):
        code, out = self.ship("start", "docs/x")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.g("branch", "--show-current").strip(), "docs/x")
        with io.open(os.path.join(self.repo, ".alaakita/expect.txt"), encoding="utf-8") as f:
            self.assertIn("先寫這裡", f.read())

    def test_s03_template_only_cannot_submit(self):
        """沒寫預期就送出 → 擋下,且沒有推送"""
        self.ship("start", "docs/x")
        self.w("README.md", u"# Demo\n\nline one\nline two\n")
        code, out = self.ship("submit", "Add line")
        self.assertEqual(code, 1, out)
        self.assertFalse(self.remote_has("docs/x"))

    def test_s04_start_refuses_main(self):
        self.assertEqual(self.ship("start", "main")[0], 2)


class Submit(ShipCase):
    def test_s05_submit_on_main_refused(self):
        code, out = self.ship("submit", "x")
        self.assertEqual(code, 1, out)
        self.assertIn("ship.py start", out)

    def test_s06_local_gate_fail_means_no_commit_no_push(self):
        self.ship("start", "docs/x")
        self.w(".alaakita/expect.txt", u"+ README.md :: something else\n")
        self.w("README.md", u"# Demo\n\nline one\nline two\n")
        head = self.g("rev-parse", "HEAD")
        code, out = self.ship("submit", "Add line")
        self.assertEqual(code, 1, out)
        self.assertIn("沒有 commit、沒有推送", out)
        self.assertEqual(self.g("rev-parse", "HEAD"), head)
        self.assertFalse(self.remote_has("docs/x"))

    def test_s07_happy_path_stops_before_merge(self):
        self.ship("start", "docs/x")
        self.good_change()
        code, out = self.ship("submit", "Add line")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.remote_has("docs/x"))
        self.assertIn("https://example.test/pull/1", out)
        calls = self.gh_state()["calls"]
        self.assertFalse(any(c[:2] == ["pr", "merge"] for c in calls), "不可自動合併")

    def test_s08_failed_check_blocks(self):
        bad = [dict(PASS3[0]), dict(PASS3[1], bucket="fail"), dict(PASS3[2])]
        self.set_gh({"checks_seq": [bad]})
        self.ship("start", "docs/x")
        self.good_change()
        code, out = self.ship("submit", "Add line")
        self.assertEqual(code, 1, out)
        self.assertIn("❌ Python 3.11", out)
        self.assertIn("失敗詳情", out)

    def test_s09_no_checks_ever_is_not_green(self):
        """檢查從沒出現 → 逾時失敗,不能當作全綠"""
        self.set_gh({"checks_seq": [None]})
        self.ship("start", "docs/x")
        self.good_change()
        code, out = self.ship("submit", "Add line")
        self.assertEqual(code, 1, out)
        self.assertIn("等不到任何檢查", out)

    def test_s10_missing_required_check_blocks(self):
        self.set_gh({"checks_seq": [PASS3[1:]]})
        self.ship("start", "docs/x")
        self.good_change()
        self.w(".alaakita/required_checks.txt", u"gate\nPython 3.11\nPython 3.13\n")
        code, out = self.ship("submit", "Add line")
        self.assertEqual(code, 1, out)
        self.assertIn("缺少必要檢查:gate", out)

    def test_s11_pending_then_pass_waits(self):
        pend = [dict(c, bucket="pending") for c in PASS3]
        self.set_gh({"checks_seq": [None, pend, PASS3]})
        self.ship("start", "docs/x")
        self.good_change()
        code, out = self.ship("submit", "Add line")
        self.assertEqual(code, 0, out)
        self.assertGreaterEqual(self.gh_state()["checks_i"], 3)

    def test_s12_existing_pr_not_duplicated(self):
        self.ship("start", "docs/x")
        self.good_change()
        self.assertEqual(self.ship("submit", "Add line")[0], 0)
        code, out = self.ship("submit", "Add line")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.gh_state()["created"], 1)
        self.assertIn("沿用既有 PR", out)


class Finish(ShipCase):
    def test_s13_finish_refused_when_not_merged(self):
        self.ship("start", "docs/x")
        self.good_change()
        self.ship("submit", "Add line")
        code, out = self.ship("finish")
        self.assertEqual(code, 1, out)
        self.assertIn("還沒合併", out)
        self.assertEqual(self.g("branch", "--show-current").strip(), "docs/x")

    def test_s14_finish_after_merge(self):
        self.ship("start", "docs/x")
        self.good_change()
        self.ship("submit", "Add line")
        # 模擬 GitHub 上合併:遠端 main 前進到分支內容
        subprocess.run(["git", "--git-dir", self.remote, "update-ref", "refs/heads/main",
                        "refs/heads/docs/x"], check=True)
        st = self.gh_state()
        st["pr"]["state"] = "MERGED"
        self.set_gh(st)
        code, out = self.ship("finish")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.g("branch", "--show-current").strip(), "main")
        self.assertNotIn("docs/x", self.g("branch", "--list", "docs/x"))
        self.assertFalse(self.remote_has("docs/x"))
        with io.open(os.path.join(self.repo, "README.md"), encoding="utf-8") as f:
            self.assertIn("line two", f.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
