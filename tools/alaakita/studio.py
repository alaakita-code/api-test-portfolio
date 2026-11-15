#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlaAkita 改動工作室 studio.py v1.0 — 一個本機網頁，把改動流程收成六步

用法(在 repo 根目錄):
  python tools/alaakita/studio.py            啟動並自動打開瀏覽器
  python tools/alaakita/studio.py --no-browser --port 8765

設計原則：
  - 只在本機：綁定 127.0.0.1，網址帶一次性通行碼，其他網站無法呼叫
  - 底層照舊：所有動作都呼叫已驗證的 ship.py，工作室不另寫一套流程
  - 不提供合併：合併一定由你在 GitHub 看完 Files changed 後按
  - 紀錄先存本機：.alaakita/local/history.jsonl(不上傳)，內容已遮蔽使用者資料夾與 token

按 Ctrl+C 結束。
"""

import argparse
import io
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import doctor  # noqa: E402  同資料夾的工具檢查(含遮蔽函式)
import ship    # noqa: E402  同資料夾的流程(取用預期檔範本)

VERSION = "1.0"
EXPECT = ".alaakita/expect.txt"
LOCAL = ".alaakita/local"
HISTORY = LOCAL + "/history.jsonl"
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,59}$")
PLACEHOLDER_RE = re.compile(r"^[+\-=] .*<[^>\n]+>", re.M)
PR_RE = re.compile(r"https?://\S+/pull/\d+")

TEMPLATES = [
    {"key": "docs", "name": "改文件", "body": u"# 本次：修改文件\n+ README.md :: <新增的文字>\n= README.md :: <必須保留的標題>\n"},
    {"key": "test", "name": "加測試", "body": u"# 本次：新增測試\n+ tests/<測試檔>.py :: def test_<新測試名稱>(\n= pytest.ini :: testpaths = tests\n"},
    {"key": "bug", "name": "修 bug", "body": u"# 本次：修正錯誤\n- <檔案> :: <錯誤的寫法>\n+ <檔案> :: <修正後的寫法>\n+ tests/<測試檔>.py :: def test_<重現這個錯誤的測試>(\n"},
    {"key": "config", "name": "改設定", "body": u"# 本次：修改設定\n+ <設定檔> :: <新的設定值>\n- <設定檔> :: <舊的設定值>\n"},
]


class Studio(object):
    def __init__(self, root, token):
        self.root = root
        self.token = token
        self.lock = threading.Lock()
        self.job = {"running": False, "action": "", "lines": [], "code": None}

    # ---------- 基本工具 ----------
    def git(self, *args):
        r = subprocess.run(["git"] + list(args), cwd=self.root, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout.strip()

    def ship(self, *args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "ship.py")] + list(args),
                           cwd=self.root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
        return r.returncode, [doctor.mask(l) for l in (r.stdout + r.stderr).splitlines()]

    def branch(self):
        return self.git("branch", "--show-current")[1]

    def expect_path(self):
        return os.path.join(self.root, EXPECT)

    def read_expect(self):
        try:
            with io.open(self.expect_path(), encoding="utf-8-sig") as f:
                return f.read()
        except IOError:
            return ""

    # ---------- 紀錄 ----------
    def record(self, action, ok, code, lines, branch="", message="", expect=None):
        os.makedirs(os.path.join(self.root, LOCAL), exist_ok=True)
        pr = ""
        for l in lines:
            m = PR_RE.search(l)
            if m:
                pr = m.group(0)
        item = {"id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": action, "ok": bool(ok), "code": code,
                "branch": doctor.mask(branch), "message": doctor.mask(message),
                "pr": pr, "lines": [doctor.mask(l) for l in lines[-80:]]}
        if expect is not None:
            item["expect"] = doctor.mask(expect)
        with io.open(os.path.join(self.root, HISTORY), "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def history(self, q=""):
        path = os.path.join(self.root, HISTORY)
        if not os.path.isfile(path):
            return []
        items = []
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except ValueError:
                    continue
        if q:
            ql = q.lower()
            items = [i for i in items if ql in json.dumps(i, ensure_ascii=False).lower()]
        return list(reversed(items))

    def local_ignored(self):
        os.makedirs(os.path.join(self.root, LOCAL), exist_ok=True)
        code, _ = self.git("check-ignore", "-q", LOCAL + "/history.jsonl")
        return code == 0

    # ---------- 動作 ----------
    def state(self):
        br = self.branch()
        _, st = self.git("status", "--porcelain")
        files = [doctor.mask(l[3:]) for l in st.splitlines() if l.strip()]
        return {"version": VERSION, "branch": br, "on_main": br in ("main", "master"),
                "files": files, "expect": self.read_expect(),
                "local_ignored": self.local_ignored(), "job": self.job_view()}

    def pr(self):
        br = self.branch()
        if br in ("main", "master", ""):
            return {"state": "", "url": ""}
        try:
            info = ship.find_pr(br) or {}
        except ship.Stop:
            info = {}
        return {"state": info.get("state", ""), "url": info.get("url", "")}

    def start(self, name):
        if not BRANCH_RE.match(name or "") or name in ("main", "master"):
            return 400, {"error": "分支名稱只能用英數字與 . _ / -，例如 docs/update-readme"}
        if self.job["running"]:
            return 409, {"error": "目前有動作在執行，請稍候"}
        if not self.local_ignored():
            return 400, {"error": "紀錄資料夾 .alaakita/local/ 沒有被 .gitignore 排除，紀錄可能被上傳。請先在 .gitignore 加入一行 .alaakita/local/"}
        code, lines = self.ship("start", name)
        self.record("start", code == 0, code, lines, branch=name)
        return 200, {"ok": code == 0, "lines": lines}

    def save_expect(self, text):
        if self.branch() in ("main", "master", ""):
            return 400, {"error": "請先在步驟 ① 開分支，再寫預期"}
        if len(text) > 20000:
            return 400, {"error": "預期檔太長"}
        with io.open(self.expect_path(), "w", encoding="utf-8", newline="") as f:
            f.write(text.replace("\r\n", "\n"))
        return 200, {"ok": True}

    def submit(self, message):
        message = (message or "").strip()
        if not message or len(message) > 200 or "\n" in message:
            return 400, {"error": "commit 訊息要一行、200 字以內"}
        if not self.local_ignored():
            return 400, {"error": "紀錄資料夾 .alaakita/local/ 沒有被 .gitignore 排除，紀錄可能被上傳。請先在 .gitignore 加入一行 .alaakita/local/"}
        expect = self.read_expect()
        if PLACEHOLDER_RE.search(expect):
            return 400, {"error": "預期檔還有 <…> 範本欄位沒填，請換成實際的檔名與文字"}
        with self.lock:
            if self.job["running"]:
                return 409, {"error": "目前有動作在執行，請稍候"}
            self.job = {"running": True, "action": "submit", "lines": [], "code": None}
        br = self.branch()

        def work():
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            with subprocess.Popen([sys.executable, "-I", os.path.join(HERE, "ship.py"), "submit", message],
                                  cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace", env=env) as p:
                for line in p.stdout:
                    self.job["lines"].append(doctor.mask(line.rstrip("\n")))
                code = p.wait()
            self.record("submit", code == 0, code, self.job["lines"], branch=br,
                        message=message, expect=expect)
            self.job["code"] = code
            self.job["running"] = False

        threading.Thread(target=work, daemon=True).start()
        return 200, {"ok": True}

    def finish(self):
        if self.job["running"]:
            return 409, {"error": "目前有動作在執行，請稍候"}
        br = self.branch()
        code, lines = self.ship("finish")
        self.record("finish", code == 0, code, lines, branch=br)
        return 200, {"ok": code == 0, "lines": lines}

    def job_view(self):
        j = self.job
        return {"running": j["running"], "action": j["action"], "lines": list(j["lines"]), "code": j["code"]}


def make_handler(studio, port):
    allowed_hosts = {"127.0.0.1:{0}".format(port), "localhost:{0}".format(port)}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def guard(self):
            if self.headers.get("Host", "") not in allowed_hosts:
                self.send(403, {"error": "只接受本機連線"})
                return False
            if self.path.startswith("/api/") and \
                    not secrets.compare_digest(self.headers.get("X-Studio-Token", ""), studio.token):
                self.send(403, {"error": "通行碼不正確，請用啟動時開啟的網址"})
                return False
            return True

        def body(self):
            n = int(self.headers.get("Content-Length", "0") or 0)
            if n > 100000:
                return {}
            try:
                return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except ValueError:
                return {}

        def do_GET(self):
            if not self.guard():
                return
            u = urlparse(self.path)
            if u.path == "/":
                return self.send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            if u.path == "/api/state":
                return self.send(200, studio.state())
            if u.path == "/api/doctor":
                return self.send(200, {"rows": doctor.collect(studio.root)})
            if u.path == "/api/templates":
                return self.send(200, {"header": ship.TEMPLATE, "items": TEMPLATES})
            if u.path == "/api/pr":
                return self.send(200, studio.pr())
            if u.path == "/api/job":
                return self.send(200, studio.job_view())
            if u.path == "/api/history":
                q = parse_qs(u.query).get("q", [""])[0]
                return self.send(200, {"items": studio.history(q)})
            self.send(404, {"error": "not found"})

        def do_POST(self):
            if not self.guard():
                return
            b = self.body()
            routes = {
                "/api/start": lambda: studio.start(str(b.get("branch", ""))),
                "/api/expect": lambda: studio.save_expect(str(b.get("text", ""))),
                "/api/submit": lambda: studio.submit(str(b.get("message", ""))),
                "/api/finish": lambda: studio.finish(),
            }
            fn = routes.get(urlparse(self.path).path)
            if not fn:
                return self.send(404, {"error": "not found"})
            code, payload = fn()
            self.send(code, payload)

    return H


def main(argv=None):
    doctor._fix_console()
    p = argparse.ArgumentParser(description="AlaAkita 改動工作室")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args(argv)
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    root = r.stdout.strip()
    if r.returncode != 0 or not os.path.isfile(os.path.join(root, ".alaakita", "gate.txt")):
        print("[停止] 請在已安裝擋關包的 repo 根目錄執行")
        return 2
    token = secrets.token_urlsafe(16)
    studio = Studio(root, token)
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(studio, a.port))
    except OSError:
        print("[停止] 連接埠 {0} 已被使用，請改用 --port 其他號碼".format(a.port))
        return 2
    url = "http://127.0.0.1:{0}/#t={1}".format(a.port, token)
    print("改動工作室已啟動：{0}".format(url))
    print("(網址含一次性通行碼，只在這台電腦有效;按 Ctrl+C 結束)")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已結束改動工作室。")
    return 0


PAGE = u"""<!DOCTYPE html>
<html lang="zh-Hant-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>改動工作室</title>
<style>
:root{--bg:#f7f3ec;--panel:#fffdf9;--ink:#2f2b26;--quiet:#7a7166;--line:#e4dccf;--accent:#3f7a72;--accent-soft:#e3efec;--warn:#a8691c;--warn-soft:#f8ecd9;--bad:#a8423a;--bad-soft:#f6e1de;--good:#3f7a52;--good-soft:#e2efe5}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 "Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;padding:18px clamp(16px,4vw,40px);border-bottom:1px solid var(--line);background:var(--panel)}
h1{margin:0;font-size:20px;font-weight:600;letter-spacing:.02em}
.chip{display:inline-block;padding:2px 10px;border-radius:999px;background:var(--accent-soft);color:var(--accent);font-size:13px;margin-left:6px}
.chip.warn{background:var(--warn-soft);color:var(--warn)}
main{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:20px;padding:20px clamp(16px,4vw,40px);max-width:1280px;margin:0 auto}
@media (max-width:900px){main{grid-template-columns:1fr}}
section.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:14px}
section.card h2{margin:0 0 4px;font-size:16px;font-weight:600;display:flex;gap:8px;align-items:center}
.num{display:inline-flex;width:24px;height:24px;border-radius:50%;background:var(--accent-soft);color:var(--accent);align-items:center;justify-content:center;font-size:13px;flex:none}
.hint{color:var(--quiet);font-size:13px;margin:2px 0 10px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=text],select,textarea{font:inherit;color:inherit;background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px 10px;min-width:0}
input[type=text]{flex:1 1 220px}
textarea{width:100%;min-height:170px;font-family:Consolas,"Cascadia Mono",monospace;font-size:13.5px;line-height:1.55;resize:vertical}
button{font:inherit;border:1px solid var(--accent);background:var(--accent);color:#fff;border-radius:8px;padding:7px 14px;cursor:pointer;white-space:nowrap}
button.ghost{background:transparent;color:var(--accent)}
button:disabled{opacity:.45;cursor:not-allowed}
pre.log{background:#fbf8f2;border:1px solid var(--line);border-radius:8px;padding:10px 12px;font:12.5px/1.55 Consolas,"Cascadia Mono",monospace;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow:auto;margin:10px 0 0}
.msg{margin-top:8px;font-size:13.5px;padding:6px 10px;border-radius:8px}
.msg.bad{background:var(--bad-soft);color:var(--bad)}.msg.good{background:var(--good-soft);color:var(--good)}.msg.warn{background:var(--warn-soft);color:var(--warn)}
ul.files{margin:6px 0 0;padding-left:20px;font-family:Consolas,monospace;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
td{padding:6px 4px;border-bottom:1px solid var(--line);vertical-align:top}
td.s{width:28px}
.hist{border-bottom:1px solid var(--line);padding:8px 0;cursor:pointer}
.hist .t{color:var(--quiet);font-size:12.5px}
.hist pre{display:none}.hist.open pre{display:block}
a{color:var(--accent)}
.locked{opacity:.55}
</style></head><body>
<header><h1>改動工作室</h1><div id="status" class="hint">讀取中…</div></header>
<main>
<div>
<section class="card" id="s1"><h2><span class="num">1</span>開始</h2>
<p class="hint">從最新的 main 開一個新分支。分支名稱用英文，例如 docs/update-readme。</p>
<div class="row"><input type="text" id="branch" placeholder="分支名稱"><button id="btnStart">開始</button></div>
<div id="m1"></div></section>

<section class="card" id="s2"><h2><span class="num">2</span>預期<span class="chip">人工確認</span></h2>
<p class="hint">先寫下這次「應該改到哪裡」。選範本後，把 &lt;…&gt; 換成實際的檔名與文字。</p>
<div class="row"><select id="tpl"></select><button class="ghost" id="btnTpl">套用範本</button><button id="btnSaveExpect">儲存預期</button></div>
<textarea id="expect" spellcheck="false"></textarea>
<div id="m2"></div></section>

<section class="card" id="s3"><h2><span class="num">3</span>修改</h2>
<p class="hint">用你的編輯器修改檔案，或請 Claude 修改。下面列出目前已修改的檔案。</p>
<div class="row"><button class="ghost" id="btnRefresh">重新整理</button></div>
<ul class="files" id="files"></ul></section>

<section class="card" id="s4"><h2><span class="num">4</span>送出</h2>
<p class="hint">本機擋關 → commit → 推送 → 開 PR → 等 GitHub 檢查。任何一步沒過就停下，不會合併。</p>
<div class="row"><input type="text" id="message" placeholder="commit 訊息(英文一行)"><button id="btnSubmit">送出</button></div>
<pre class="log" id="log" hidden></pre><div id="m4"></div></section>

<section class="card" id="s5"><h2><span class="num">5</span>審查<span class="chip">人工確認</span></h2>
<p class="hint">打開 PR 的 Files changed，確認內容正確後，在 GitHub 按 Merge pull request。工作室不提供合併按鈕。</p>
<div class="row"><a id="prLink" target="_blank" rel="noopener" hidden>打開 PR 的 Files changed</a><button class="ghost" id="btnPr">檢查是否已合併</button></div>
<div id="m5"></div></section>

<section class="card" id="s6"><h2><span class="num">6</span>收尾</h2>
<p class="hint">確認已合併後才能按：切回 main、同步、刪除本地與 GitHub 上的分支。</p>
<div class="row"><button id="btnFinish" disabled>收尾</button></div>
<div id="m6"></div></section>
</div>

<div>
<section class="card"><h2>環境檢查</h2><p class="hint">與 Claude 配合前先看這裡全是 ✅。內容已遮蔽，可直接複製給 Claude。</p>
<div class="row"><button class="ghost" id="btnDoctor">重新檢查</button><button class="ghost" id="btnCopyDoctor">複製結果</button></div>
<table id="doctor"></table></section>
<section class="card"><h2>紀錄</h2><p class="hint">每個動作都會記錄(只存在這台電腦)。點一筆可看細節。</p>
<div class="row"><input type="text" id="q" placeholder="搜尋分支、訊息、PR…"><button class="ghost" id="btnSearch">搜尋</button></div>
<div id="hist"></div></section>
</div>
</main>
<script>
var TOKEN = (location.hash.match(/t=([A-Za-z0-9_\\-]+)/) || [])[1] || '';
var templates = {header: '', items: []};
var doctorText = '';
function $(id){ return document.getElementById(id); }
function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function api(method, path, body, cb){
  var x = new XMLHttpRequest();
  x.open(method, path, true);
  x.setRequestHeader('X-Studio-Token', TOKEN);
  x.setRequestHeader('Content-Type', 'application/json');
  x.onload = function(){ var d = {}; try { d = JSON.parse(x.responseText); } catch (e) {} cb(x.status, d); };
  x.onerror = function(){ cb(0, {error: '連不到工作室，請確認 PowerShell 視窗還開著'}); };
  x.send(body ? JSON.stringify(body) : null);
}
function msg(id, text, kind){ $(id).innerHTML = text ? '<div class="msg ' + (kind || '') + '">' + esc(text) + '</div>' : ''; }
function lastLines(lines){ return (lines || []).slice(-6).join('\\n'); }
function loadState(){
  api('GET', '/api/state', null, function(s, d){
    if (s !== 200) { $('status').innerHTML = '<span class="chip warn">' + esc(d.error || '無法讀取') + '</span>'; return; }
    var chip = d.on_main ? '在 main' : '分支 ' + d.branch;
    $('status').innerHTML = '目前<span class="chip">' + esc(chip) + '</span>' +
      (d.files.length ? '<span class="chip warn">' + d.files.length + ' 個未提交修改</span>' : '') +
      (d.local_ignored ? '' : '<span class="chip warn">紀錄資料夾未排除上傳</span>');
    $('btnStart').disabled = !d.on_main || d.files.length > 0 || d.job.running;
    if (d.on_main && d.files.length) msg('m1', '有未提交的修改，請先處理再開始。', 'warn');
    var notBranch = d.on_main;
    $('btnSaveExpect').disabled = notBranch; $('btnTpl').disabled = notBranch;
    $('btnSubmit').disabled = notBranch || d.job.running;
    if (document.activeElement !== $('expect') && !$('expect').dataset.dirty) $('expect').value = d.expect;
    var ul = $('files'); ul.innerHTML = '';
    if (!d.files.length) ul.innerHTML = '<li class="hint">沒有已修改的檔案</li>';
    for (var i = 0; i < d.files.length; i++) ul.innerHTML += '<li>' + esc(d.files[i]) + '</li>';
    if (d.job.running) poll();
  });
}
function loadTemplates(){
  api('GET', '/api/templates', null, function(s, d){
    if (s !== 200) return;
    templates = d; var sel = $('tpl'); sel.innerHTML = '';
    for (var i = 0; i < d.items.length; i++) sel.innerHTML += '<option value="' + i + '">' + esc(d.items[i].name) + '</option>';
  });
}
function loadDoctor(){
  $('doctor').innerHTML = '<tr><td class="hint">檢查中…</td></tr>';
  api('GET', '/api/doctor', null, function(s, d){
    if (s !== 200) return;
    var mark = {ok: '✅', warn: '⚠️', fail: '❌'}, h = '', t = [];
    for (var i = 0; i < d.rows.length; i++) {
      var r = d.rows[i];
      h += '<tr><td class="s">' + mark[r.status] + '</td><td><b>' + esc(r.item) + '</b>:' + esc(r.value) +
        (r.hint && r.status !== 'ok' ? '<div class="hint">' + esc(r.hint) + '</div>' : '') + '</td></tr>';
      t.push(mark[r.status] + ' ' + r.item + ':' + r.value + (r.hint && r.status !== 'ok' ? '\\n   → ' + r.hint : ''));
    }
    $('doctor').innerHTML = h; doctorText = t.join('\\n');
  });
}
function loadHistory(){
  api('GET', '/api/history?q=' + encodeURIComponent($('q').value), null, function(s, d){
    if (s !== 200) return;
    var names = {start: '開始', submit: '送出', finish: '收尾'}, h = '';
    if (!d.items.length) h = '<p class="hint">還沒有紀錄</p>';
    for (var i = 0; i < d.items.length; i++) {
      var it = d.items[i];
      h += '<div class="hist" data-i="' + i + '"><div>' + (it.ok ? '✅' : '❌') + ' ' + esc(names[it.action] || it.action) +
        ' · ' + esc(it.branch) + (it.message ? ' · ' + esc(it.message) : '') + '</div><div class="t">' + esc(it.time) +
        (it.pr ? ' · <a href="' + esc(it.pr) + '" target="_blank" rel="noopener">PR</a>' : '') + '</div><pre class="log">' +
        esc((it.expect ? '【預期】\\n' + it.expect + '\\n【過程】\\n' : '') + (it.lines || []).join('\\n')) + '</pre></div>';
    }
    $('hist').innerHTML = h;
    var nodes = $('hist').querySelectorAll('.hist');
    for (var j = 0; j < nodes.length; j++) nodes[j].onclick = function(e){ if (e.target.tagName !== 'A') this.classList.toggle('open'); };
  });
}
var polling = false;
function poll(){
  if (polling) return; polling = true; $('log').hidden = false;
  (function tick(){
    api('GET', '/api/job', null, function(s, j){
      $('log').textContent = (j.lines || []).join('\\n'); $('log').scrollTop = $('log').scrollHeight;
      if (j.running) { setTimeout(tick, 1500); return; }
      polling = false; $('btnSubmit').disabled = false;
      if (j.code === 0) { msg('m4', '全部通過。請到步驟 5 打開 PR 審查。', 'good'); checkPr(false); }
      else if (j.code !== null) msg('m4', '沒有全綠，已停下。請看上方紀錄的停止原因。', 'bad');
      loadState(); loadHistory();
    });
  })();
}
function checkPr(quiet){
  if (!quiet) msg('m5', '查詢 PR 狀態中…');
  api('GET', '/api/pr', null, function(s, d){
    if (!d.url) { msg('m5', quiet ? '' : '目前分支還沒有 PR。', 'warn'); $('prLink').hidden = true; $('btnFinish').disabled = true; return; }
    $('prLink').href = d.url + '/files'; $('prLink').hidden = false;
    var merged = d.state === 'MERGED';
    $('btnFinish').disabled = !merged;
    msg('m5', merged ? '已合併，可以到步驟 6 收尾。' : '尚未合併(' + d.state + ')。看完 Files changed 後在 GitHub 按合併，再按「檢查是否已合併」。', merged ? 'good' : 'warn');
  });
}
$('btnStart').onclick = function(){
  var b = $('branch').value.trim(); msg('m1', '建立中…');
  api('POST', '/api/start', {branch: b}, function(s, d){
    if (s !== 200) { msg('m1', d.error, 'bad'); return; }
    msg('m1', d.ok ? '已建立分支，接著到步驟 2 寫預期。' : lastLines(d.lines), d.ok ? 'good' : 'bad');
    $('expect').dataset.dirty = ''; loadState(); loadHistory();
  });
};
$('btnTpl').onclick = function(){
  var it = templates.items[+$('tpl').value]; if (!it) return;
  $('expect').value = templates.header + '\\n' + it.body; $('expect').dataset.dirty = '1';
  msg('m2', '已套用範本，請把 <…> 換成實際內容後按「儲存預期」。', 'warn');
};
$('expect').oninput = function(){ this.dataset.dirty = '1'; };
$('btnSaveExpect').onclick = function(){
  api('POST', '/api/expect', {text: $('expect').value}, function(s, d){
    if (s !== 200) { msg('m2', d.error, 'bad'); return; }
    $('expect').dataset.dirty = '';
    var left = /^[+\\-=] .*<[^>\\n]+>/m.test($('expect').value);
    msg('m2', left ? '已儲存，但還有 <…> 欄位沒填，送出時會被擋下。' : '已儲存。', left ? 'warn' : 'good');
  });
};
$('btnRefresh').onclick = loadState;
$('btnSubmit').onclick = function(){
  if ($('expect').dataset.dirty) { msg('m4', '預期有修改還沒儲存，請先在步驟 2 按「儲存預期」。', 'warn'); return; }
  msg('m4', ''); $('btnSubmit').disabled = true;
  api('POST', '/api/submit', {message: $('message').value}, function(s, d){
    if (s !== 200) { msg('m4', d.error, 'bad'); $('btnSubmit').disabled = false; return; }
    poll();
  });
};
$('btnPr').onclick = function(){ checkPr(false); };
$('btnFinish').onclick = function(){
  msg('m6', '收尾中…');
  api('POST', '/api/finish', null, function(s, d){
    if (s !== 200) { msg('m6', d.error, 'bad'); return; }
    msg('m6', d.ok ? '已收尾，回到 main。可以開始下一個改動。' : lastLines(d.lines), d.ok ? 'good' : 'bad');
    $('btnFinish').disabled = true; $('prLink').hidden = true; loadState(); loadHistory();
  });
};
$('btnDoctor').onclick = loadDoctor;
$('btnCopyDoctor').onclick = function(){
  var ta = document.createElement('textarea'); ta.value = 'AlaAkita 工具基本檢查\\n' + doctorText; document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy'); } catch (e) {} document.body.removeChild(ta);
};
$('btnSearch').onclick = loadHistory;
$('q').onkeydown = function(e){ if (e.key === 'Enter') loadHistory(); };
if (!TOKEN) $('status').textContent = '缺少通行碼，請用 PowerShell 顯示的網址開啟';
else { loadState(); loadTemplates(); loadDoctor(); loadHistory(); checkPr(true); }
</script></body></html>
"""

if __name__ == "__main__":
    sys.exit(main())
