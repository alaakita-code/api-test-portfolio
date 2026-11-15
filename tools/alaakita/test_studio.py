#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
studio.py 與 doctor.py 雙向陷阱測試:真的啟動本機伺服器,以 HTTP 呼叫各端點。
遠端用暫存 bare repo,gh 用 test_ship.py 的假 gh。
執行:python3 test_studio.py
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import doctor  # noqa: E402
import studio  # noqa: E402
from test_ship import FAKE_GH, PASS3  # noqa: E402

TOKEN = "test-token-123456"


class StudioCase(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="studio_")
        self.remote = os.path.join(self.d, "remote.git")
        self.repo = os.path.join(self.d, "repo")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.remote], check=True)
        os.makedirs(self.repo)
        self.g("init", "-q", "-b", "main")
        self.g("config", "user.email", "t@t")
        self.g("config", "user.name", "t")
        self.w(".alaakita/gate.txt", u"test    \"{0}\" -c \"print('ok')\"\n".format(sys.executable))
        self.w(".alaakita/expect.txt", u"# base\n")
        self.w(".gitignore", u".alaakita/local/\n")
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
        self.env_backup = dict(os.environ)
        os.environ.update(SHIP_GH=self.fake, FAKE_GH_STATE=self.state,
                          SHIP_POLL_SECONDS="0", SHIP_TIMEOUT_SECONDS="0.5")
        self.st = studio.Studio(self.repo, TOKEN)
        self.srv = studio.ThreadingHTTPServer(("127.0.0.1", 0), studio.make_handler(self.st, 0))
        self.port = self.srv.server_address[1]
        self.srv.RequestHandlerClass = studio.make_handler(self.st, self.port)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        os.environ.clear()
        os.environ.update(self.env_backup)
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

    def gh_calls(self):
        with io.open(self.state, encoding="utf-8") as f:
            return json.load(f).get("calls", [])

    def call(self, method, path, body=None, token=TOKEN, host=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request("http://127.0.0.1:{0}{1}".format(self.port, path), data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if token is not None:
            req.add_header("X-Studio-Token", token)
        if host:
            req.add_header("Host", host)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8")
                return r.status, (json.loads(raw) if path.startswith("/api/") else raw)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")

    def wait_job(self):
        for _ in range(300):
            s, j = self.call("GET", "/api/job")
            if not j["running"]:
                return j
            time.sleep(0.1)
        self.fail("job did not finish")

    def good_change(self):
        self.assertEqual(self.call("POST", "/api/start", {"branch": "docs/x"})[0], 200)
        s, d = self.call("POST", "/api/expect", {"text": "+ README.md :: line two\n= README.md :: line one\n"})
        self.assertEqual(s, 200, d)
        self.w("README.md", u"# Demo\n\nline one\nline two\n")


class Security(StudioCase):
    def test_st01_api_needs_token(self):
        self.assertEqual(self.call("GET", "/api/state", token=None)[0], 403)
        self.assertEqual(self.call("GET", "/api/state", token="wrong")[0], 403)
        self.assertEqual(self.call("GET", "/api/state")[0], 200)

    def test_st02_foreign_host_rejected(self):
        """防 DNS rebinding:Host 不是本機就拒絕,連首頁也不給"""
        self.assertEqual(self.call("GET", "/", host="evil.example:{0}".format(self.port))[0], 403)
        self.assertEqual(self.call("GET", "/api/state", host="evil.example")[0], 403)

    def test_st03_no_merge_anywhere(self):
        self.assertEqual(self.call("POST", "/api/merge", {})[0], 404)
        self.good_change()
        self.call("POST", "/api/submit", {"message": "Add line"})
        self.wait_job()
        self.assertFalse(any(c[:2] == ["pr", "merge"] for c in self.gh_calls()))

    def test_st04_page_is_offline(self):
        s, html = self.call("GET", "/")
        self.assertEqual(s, 200)
        self.assertNotIn("http://", html.replace("http://127.0.0.1", ""))
        self.assertNotIn("https://", html)
        self.assertIn("[hidden]{display:none!important}", html)
        self.assertIn("width=device-width", html)


class Flow(StudioCase):
    def test_st05_start_validates_branch(self):
        self.assertEqual(self.call("POST", "/api/start", {"branch": "bad name;rm"})[0], 400)
        self.assertEqual(self.call("POST", "/api/start", {"branch": "main"})[0], 400)
        s, d = self.call("POST", "/api/start", {"branch": "docs/x"})
        self.assertTrue(d["ok"], d)
        self.assertEqual(self.g("branch", "--show-current").strip(), "docs/x")

    def test_st06_expect_needs_branch(self):
        self.assertEqual(self.call("POST", "/api/expect", {"text": "x"})[0], 400)

    def test_st07_placeholder_blocks_submit(self):
        self.call("POST", "/api/start", {"branch": "docs/x"})
        self.call("POST", "/api/expect", {"text": "+ README.md :: <新增的文字>\n"})
        s, d = self.call("POST", "/api/submit", {"message": "Add line"})
        self.assertEqual(s, 400)
        self.assertIn("範本欄位", d["error"])

    def test_st08_submit_happy_and_recorded(self):
        self.good_change()
        s, d = self.call("POST", "/api/submit", {"message": "Add line"})
        self.assertEqual(s, 200, d)
        j = self.wait_job()
        self.assertEqual(j["code"], 0, j)
        items = self.call("GET", "/api/history")[1]["items"]
        self.assertEqual(items[0]["action"], "submit")
        self.assertTrue(items[0]["ok"])
        self.assertEqual(items[0]["pr"], "https://example.test/pull/1")
        self.assertIn("line two", items[0]["expect"])
        self.assertEqual(self.g("status", "--porcelain").strip(), "", "紀錄檔不可出現在 git 的未提交清單")

    def test_st09_failed_checks_recorded_as_failure(self):
        bad = [dict(PASS3[0], bucket="fail")] + PASS3[1:]
        self.set_gh({"checks_seq": [bad]})
        self.good_change()
        self.call("POST", "/api/submit", {"message": "Add line"})
        j = self.wait_job()
        self.assertEqual(j["code"], 1)
        self.assertFalse(self.call("GET", "/api/history")[1]["items"][0]["ok"])

    def test_st10_finish_refused_until_merged(self):
        self.good_change()
        self.call("POST", "/api/submit", {"message": "Add line"})
        self.wait_job()
        s, d = self.call("POST", "/api/finish")
        self.assertFalse(d["ok"])
        self.assertEqual(self.g("branch", "--show-current").strip(), "docs/x")

    def test_st11_history_search(self):
        self.call("POST", "/api/start", {"branch": "docs/alpha"})
        items = self.call("GET", "/api/history?q=alpha")[1]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(len(self.call("GET", "/api/history?q=nomatch")[1]["items"]), 0)

    def test_st12_refuse_when_history_not_ignored(self):
        """紀錄沒被 .gitignore 排除 → 拒絕開始,避免紀錄被 commit 上傳"""
        self.w(".gitignore", u"")
        self.g("commit", "-qam", "drop ignore")
        s, d = self.call("POST", "/api/start", {"branch": "docs/x"})
        self.assertEqual(s, 400)
        self.assertIn(".gitignore", d["error"])


class Masking(StudioCase):
    def test_st13_record_masks_home_and_tokens(self):
        home = os.path.expanduser("~")
        self.st.record("submit", True, 0, [home + "/secret/path", "token=abc123", "ghp_ABCDEFGHIJKLMNOP1234"],
                       branch="x", message=home)
        with io.open(os.path.join(self.repo, studio.HISTORY), encoding="utf-8") as f:
            raw = f.read()
        self.assertNotIn(home, raw)
        self.assertNotIn("abc123", raw)
        self.assertNotIn("ghp_ABCDEFGH", raw)
        self.assertIn("~/secret/path", raw)

    def test_st14_doctor_output_masked(self):
        home = os.path.expanduser("~")
        rows = doctor.collect()
        self.assertTrue(rows)
        self.assertNotIn(home, json.dumps(rows, ensure_ascii=False))
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "doctor.py")], cwd=self.repo,
                           capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        self.assertNotIn(home, r.stdout)
        self.assertIn("工具基本檢查", r.stdout)

    def test_st15_mask_windows_style_paths(self):
        orig = os.path.expanduser
        try:
            os.path.expanduser = lambda p: "C:\\Users\\someone" if p == "~" else orig(p)
            out = doctor.mask("C:\\Users\\someone\\Desktop\\proj and c:/users/SOMEONE/x")
        finally:
            os.path.expanduser = orig
        self.assertNotIn("someone", out.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
