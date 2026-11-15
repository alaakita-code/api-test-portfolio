#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
path_check.py 雙向陷阱測試(D-007:攔得住 + 不誤判,兩個方向都要測)

執行:python3 test_path_check.py
可選:設定環境變數 VERIFY_PY=verify.py 路徑,T01 會同時證明「verify 全綠、路徑檢查擋下」
"""

import functools
import http.server
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.environ.get("PATH_CHECK_PY", os.path.join(HERE, "path_check.py"))

OLD_HTML = u"""﻿<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div id="app"><div class="tab">內容</div></div>
<script>
function svgRoad(){ return '<svg></svg>'; }
function renderLab(){ var x = 1; return x; }
</script></body></html>
"""

NEW_HTML = OLD_HTML.replace(
    "function renderLab()",
    "function renderArch(){ return svgRoad(); }\nfunction renderLab()")


def run(*args):
    r = subprocess.run([sys.executable, "-I", CHECKER] + list(args),
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="pc_")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def w(self, rel, text):
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return p


class SingleFile(Base):
    def test_t01_atlas_unchanged_file_is_blocked(self):
        """知識庫 v3.7 事故:寫入失敗、檔案沒變,verify 全綠,路徑檢查必須擋下"""
        b = self.w("old.html", OLD_HTML)
        a = self.w("new.html", OLD_HTML)
        e = self.w("expect.txt", "+ function renderArch(\n")
        code, out = run("--before", b, "--after", a, "--expect", e)
        self.assertEqual(code, 1, out)
        self.assertIn("修改前後完全相同", out)
        vp = os.environ.get("VERIFY_PY")
        if vp:
            r = subprocess.run([sys.executable, "-I", vp, a], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, "此樣本 verify 應全綠,才證明兩者互補:\n" + r.stdout)

    def test_t02_clean_change_passes(self):
        b = self.w("old.html", OLD_HTML)
        a = self.w("new.html", NEW_HTML)
        e = self.w("expect.txt", "# 新增架構圖\n+ function renderArch(\n= function renderLab(\n")
        code, out = run("--before", b, "--after", a, "--expect", e)
        self.assertEqual(code, 0, out)

    def test_t03_preexisting_token_not_counted(self):
        """標記修改前就存在:只檢查「有出現」會誤判通過"""
        b = self.w("old.html", OLD_HTML)
        a = self.w("new.html", OLD_HTML.replace("內容", "內容二"))
        e = self.w("expect.txt", "+ function svgRoad(\n")
        code, out = run("--before", b, "--after", a, "--expect", e)
        self.assertEqual(code, 1, out)
        self.assertIn("修改前就已存在", out)

    def test_t04_removal(self):
        b = self.w("old.html", OLD_HTML)
        e = self.w("expect.txt", "- var x = 1;\n")
        still = self.w("still.html", OLD_HTML.replace("內容", "內容二"))
        self.assertEqual(run("--before", b, "--after", still, "--expect", e)[0], 1)
        done = self.w("done.html", OLD_HTML.replace("var x = 1;", "var x = 2;"))
        self.assertEqual(run("--before", b, "--after", done, "--expect", e)[0], 0)

    def test_t05_removal_of_nonexistent_token_proves_nothing(self):
        b = self.w("old.html", OLD_HTML)
        a = self.w("new.html", NEW_HTML)
        e = self.w("expect.txt", "- 根本不存在的字串\n")
        code, out = run("--before", b, "--after", a, "--expect", e)
        self.assertEqual(code, 1, out)
        self.assertIn("無法證明任何事", out)

    def test_t06_keep_rule_catches_accidental_delete(self):
        b = self.w("old.html", OLD_HTML)
        a = self.w("new.html", NEW_HTML.replace("function svgRoad(){ return '<svg></svg>'; }", ""))
        e = self.w("expect.txt", "+ function renderArch(\n= function svgRoad(\n")
        self.assertEqual(run("--before", b, "--after", a, "--expect", e)[0], 1)

    def test_t07_shrink_guard(self):
        b = self.w("old.html", OLD_HTML + ("<!-- 填充 -->\n" * 200))
        a = self.w("new.html", NEW_HTML)
        e = self.w("expect.txt", "+ function renderArch(\n")
        code, out = run("--before", b, "--after", a, "--expect", e)
        self.assertEqual(code, 1, out)
        self.assertIn("大小檢查", out)


class TreeMode(Base):
    def make(self, root, index_js, fn_js):
        self.w(root + "/src/index.js", index_js)
        self.w(root + "/functions/api/[[path]].js", fn_js)
        self.w(root + "/wrangler.toml", 'main = "src/index.js"\n')

    def test_t08_oss_dead_code_change_is_blocked(self):
        """OSS 事故:改到不會執行的 functions/,部署成功但實際路由沒變"""
        self.make("old", "route('/a');\n", "old();\n")
        self.make("new", "route('/a');\n", "old();\nfunction handleUpdateIncidentStatus(){}\n")
        e = self.w("expect.txt", "+ src/index.js :: handleUpdateIncidentStatus\n")
        code, out = run("--before", os.path.join(self.d, "old"),
                        "--after", os.path.join(self.d, "new"), "--expect", e)
        self.assertEqual(code, 1, out)

    def test_t09_correct_file_passes(self):
        self.make("old", "route('/a');\n", "old();\n")
        self.make("new", "route('/a');\nfunction handleUpdateIncidentStatus(){}\n", "old();\n")
        e = self.w("expect.txt", "+ src/index.js :: handleUpdateIncidentStatus\n")
        code, out = run("--before", os.path.join(self.d, "old"),
                        "--after", os.path.join(self.d, "new"), "--expect", e)
        self.assertEqual(code, 0, out)

    def test_t16_tree_nothing_changed_is_blocked(self):
        """只有「保留」規則時,資料夾完全沒變也必須擋下(突變測試 M6 找到的缺口)"""
        self.make("old", "route('/a');\n", "old();\n")
        self.make("new", "route('/a');\n", "old();\n")
        e = self.w("expect.txt", "= src/index.js :: route('/a')\n")
        code, out = run("--before", os.path.join(self.d, "old"),
                        "--after", os.path.join(self.d, "new"), "--expect", e)
        self.assertEqual(code, 1, out)
        self.assertIn("沒有任何檔案變動", out)

    def test_t17_ignore_excludes_expect_file_from_change_detection(self):
        """CI 情境:只改了預期檔本身,不算真正改動"""
        self.make("old", "route('/a');\n", "old();\n")
        self.make("new", "route('/a');\n", "old();\n")
        self.w("old/.alaakita/expect.txt", "= x\n")
        self.w("new/.alaakita/expect.txt", "= y\n")
        e = self.w("expect.txt", "= src/index.js :: route('/a')\n")
        args = ["--before", os.path.join(self.d, "old"), "--after", os.path.join(self.d, "new"), "--expect", e]
        self.assertEqual(run(*args)[0], 0)
        code, out = run(*(args + ["--ignore", ".alaakita/*"]))
        self.assertEqual(code, 1, out)
        self.assertIn("沒有任何檔案變動", out)

    def test_t18_git_ignored_files_are_not_changes(self):
        """v1.2:被 .gitignore 排除的檔案(報告、虛擬環境)不算改動,也不讀取"""
        repo = os.path.join(self.d, "repo")
        self.make("repo", "route('/a');\n", "old();\n")
        self.w("repo/.gitignore", "reports/\n")
        g = lambda *a: subprocess.run(["git", "-C", repo] + list(a), capture_output=True, check=True)
        g("init", "-q")
        g("add", "-A")
        g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
        self.w("repo/reports/report.html", "<html>new report</html>\n")
        e = self.w("expect.txt", "= src/index.js :: route('/a')\n")
        code, out = run("--before-git", "HEAD", "--after", repo, "--expect", e)
        self.assertEqual(code, 1, out)
        self.assertIn("沒有任何檔案變動", out)

    def test_t19_venv_skipped_outside_git(self):
        self.make("old", "a\n", "b\n")
        self.make("new", "a\n", "b\n")
        self.w("new/.venv/lib/x.py", "x = 1\n")
        e = self.w("expect.txt", "= src/index.js :: a\n")
        code, out = run("--before", os.path.join(self.d, "old"),
                        "--after", os.path.join(self.d, "new"), "--expect", e)
        self.assertEqual(code, 1, out)
        self.assertIn("沒有任何檔案變動", out)

    def test_t10_tree_rule_without_file_is_usage_error(self):
        self.make("old", "a\n", "b\n")
        self.make("new", "a2\n", "b\n")
        e = self.w("expect.txt", "+ a2\n")
        self.assertEqual(run("--before", os.path.join(self.d, "old"),
                             "--after", os.path.join(self.d, "new"), "--expect", e)[0], 2)

    def test_t11_git_mode(self):
        repo = os.path.join(self.d, "repo")
        self.make("repo", "route('/a');\n", "old();\n")
        g = lambda *a: subprocess.run(["git", "-C", repo] + list(a), capture_output=True, check=True)
        g("init", "-q")
        g("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
        e = self.w("expect.txt", "+ src/index.js :: handleUpdateIncidentStatus\n")
        self.assertEqual(run("--before-git", "HEAD", "--after", repo, "--expect", e)[0], 1)
        self.w("repo/src/index.js", "route('/a');\nfunction handleUpdateIncidentStatus(){}\n")
        code, out = run("--before-git", "HEAD", "--after", repo, "--expect", e)
        self.assertEqual(code, 0, out)


class Manifest(Base):
    def test_t12_empty_manifest_refused(self):
        b = self.w("old.html", OLD_HTML)
        a = self.w("new.html", NEW_HTML)
        e = self.w("expect.txt", "# 只有註解\n\n")
        code, out = run("--before", b, "--after", a, "--expect", e)
        self.assertEqual(code, 2, out)
        self.assertIn("拒絕判定通過", out)

    def test_t13_bad_syntax(self):
        b = self.w("old.html", OLD_HTML)
        a = self.w("new.html", NEW_HTML)
        e = self.w("expect.txt", "+renderArch\n")
        self.assertEqual(run("--before", b, "--after", a, "--expect", e)[0], 2)

    def test_t14_type_mismatch(self):
        b = self.w("old.html", OLD_HTML)
        os.makedirs(os.path.join(self.d, "dir"))
        e = self.w("expect.txt", "+ x\n")
        self.assertEqual(run("--before", b, "--after", os.path.join(self.d, "dir"), "--expect", e)[0], 2)


class UrlMode(Base):
    def test_t15_deployed_page_must_show_new_marker(self):
        """「部署成功、版本號更新」不算數,線上頁面要真的出現新標記"""
        site = os.path.join(self.d, "site")
        os.makedirs(site)
        b = self.w("old.html", OLD_HTML)
        self.w("site/index.html", OLD_HTML)
        e = self.w("expect.txt", "+ function renderArch(\n")
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        handler = functools.partial(Quiet, directory=site)
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            url = "http://127.0.0.1:{0}/index.html".format(srv.server_address[1])
            self.assertEqual(run("--before", b, "--after", url, "--expect", e)[0], 1)
            self.w("site/index.html", NEW_HTML)
            code, out = run("--before", b, "--after", url, "--expect", e)
            self.assertEqual(code, 0, out)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
