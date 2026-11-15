#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlaAkita 工具基本檢查 doctor.py v1.0 — 與 Claude 配合前，先確認工具狀況

用法：
  python doctor.py            在任何資料夾執行;在 repo 內會多檢查 repo 狀態
  python doctor.py --json     給改動工作室使用

輸出已遮蔽：使用者資料夾顯示為 ~，長得像 token 的字串顯示為 ****,
可以直接整段貼給 Claude。

exit code:0 沒有 ❌(可以開始) / 1 至少一項 ❌
"""

import json
import os
import re
import shutil
import subprocess
import sys

VERSION = "1.0"
OK, WARN, FAIL = "ok", "warn", "fail"
MARK = {OK: "✅", WARN: "⚠️", FAIL: "❌"}
CWD = None  # 改動工作室指定 repo 根目錄;單獨執行時為目前資料夾

TOKEN_RE = re.compile(r"(gh[pousr]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}|sk-[A-Za-z0-9_\-]{8,}"
                      r"|(?i:bearer)\s+[A-Za-z0-9._\-]{8,}|(?i:token|password|passwd|secret)\s*[=:]\s*\S+)")


def mask(text):
    """遮蔽使用者資料夾與 token。改動工作室的紀錄也用這個函式。"""
    if not text:
        return text
    home = os.path.expanduser("~")
    out = str(text)
    if home and len(home) > 3:
        for h in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
            out = re.sub(re.escape(h), "~", out, flags=re.I)
    out = TOKEN_RE.sub("****", out)
    return out


def _fix_console():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, cwd=CWD)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""


def first_line(s):
    for line in (s or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def check_python():
    v = sys.version_info
    ver = "{0}.{1}.{2}".format(v[0], v[1], v[2])
    if v < (3, 9):
        return FAIL, "Python", ver, "版本太舊，請安裝 3.11 以上：python.org 下載 Windows 安裝檔，勾選 Add python.exe to PATH"
    return OK, "Python", ver, ""


def check_git():
    if not shutil.which("git"):
        hint = "找不到 git。"
        if os.name == "nt" and os.path.isfile(r"C:\Program Files\Git\cmd\git.exe"):
            hint += "已安裝但不在 PATH:執行 $env:Path += \";C:\\Program Files\\Git\\cmd\" 後重試"
        else:
            hint += "請安裝 Git for Windows(git-scm.com)，安裝時保留「Git from the command line」選項"
        return [(FAIL, "Git", "未找到", hint)]
    code, out = run(["git", "--version"])
    rows = [(OK, "Git", first_line(out).replace("git version ", ""), "")]
    _, name = run(["git", "config", "user.name"])
    _, email = run(["git", "config", "user.email"])
    name = first_line(name)
    if not name or not first_line(email):
        rows.append((FAIL, "Git 作者資訊", "未設定",
                     "執行 git config --global user.name \"你的名字\" 與 git config --global user.email \"信箱\""))
    else:
        rows.append((OK, "Git 作者名稱", name, "commit 會以這個名字顯示;不對就用 git config user.name 修改"))
    return rows


def check_gh():
    if not shutil.which("gh"):
        return [(FAIL, "GitHub CLI(gh)", "未找到",
                 "執行 winget install --id GitHub.cli -e --source winget，或到 cli.github.com 下載;裝完重開 PowerShell")]
    _, out = run(["gh", "--version"])
    rows = [(OK, "GitHub CLI(gh)", first_line(out).replace("gh version ", "").split(" ")[0], "")]
    code, _ = run(["gh", "auth", "status"])  # 輸出不顯示，避免帶出帳號細節
    if code == 0:
        rows.append((OK, "GitHub 登入", "已登入", ""))
    else:
        rows.append((FAIL, "GitHub 登入", "未登入",
                     "執行 gh auth login:GitHub.com → HTTPS → Y → Login with a web browser"))
    return rows


def check_node():
    if not shutil.which("node"):
        return WARN, "Node.js", "未找到", "只有單檔 HTML 工具的驗收(verify.py)需要;不做 HTML 可略過"
    _, out = run(["node", "--version"])
    return OK, "Node.js", first_line(out), ""


def check_winget():
    if os.name != "nt":
        return None
    if not shutil.which("winget"):
        return WARN, "winget", "未找到", "安裝其他工具時改用官方安裝檔即可"
    return OK, "winget", "可用", "第一次使用若詢問 msstore 條款，可按 Y，或在指令加 --source winget"


def check_repo():
    code, top = run(["git", "rev-parse", "--show-toplevel"])
    if code != 0:
        return [(WARN, "目前資料夾", "不在 git repo 內", "要檢查 repo 狀態，請 cd 到專案資料夾再執行")]
    top = first_line(top)
    rows = []
    home = os.path.expanduser("~")
    if os.path.normcase(os.path.abspath(top)).startswith(os.path.normcase(os.path.abspath(home))):
        rows.append((WARN, "專案路徑", mask(top),
                     "路徑含使用者名稱;貼給 AI 前請用本工具的遮蔽輸出，或把專案搬到 C:\\dev\\ 這類路徑"))
    else:
        rows.append((OK, "專案路徑", top, ""))
    _, br = run(["git", "branch", "--show-current"])
    _, st = run(["git", "status", "--porcelain"])
    dirty = len([l for l in st.splitlines() if l.strip()])
    rows.append((OK if dirty == 0 else WARN, "分支與修改",
                 "{0},{1}".format(first_line(br) or "(detached)", "沒有未提交的修改" if dirty == 0 else "{0} 個未提交的修改".format(dirty)),
                 "" if dirty == 0 else "開始新改動前請先 commit 或還原"))
    code, url = run(["git", "remote", "get-url", "origin"])
    if code != 0:
        rows.append((FAIL, "GitHub 遠端", "未設定 origin", "這個 repo 還沒連到 GitHub"))
    else:
        rows.append((OK, "GitHub 遠端", mask(first_line(url)), ""))
    gate = os.path.isfile(os.path.join(top, ".alaakita", "gate.txt"))
    rows.append((OK if gate else WARN, "擋關設定", "已安裝" if gate else "未安裝",
                 "" if gate else "這個 repo 尚未安裝擋關包"))
    return rows


def collect(cwd=None):
    global CWD
    CWD = cwd
    rows = [check_python()]
    rows += check_git()
    rows += check_gh()
    rows.append(check_node())
    w = check_winget()
    if w:
        rows.append(w)
    if shutil.which("git"):
        rows += check_repo()
    return [{"status": s, "item": i, "value": mask(v), "hint": mask(h)} for s, i, v, h in rows]


def main(argv=None):
    _fix_console()
    argv = sys.argv[1:] if argv is None else argv
    rows = collect()
    failed = [r for r in rows if r["status"] == FAIL]
    if "--json" in argv:
        print(json.dumps({"version": VERSION, "rows": rows, "ready": not failed}, ensure_ascii=False))
        return 0 if not failed else 1
    print("AlaAkita 工具基本檢查 v{0}(輸出已遮蔽，可直接貼給 Claude)".format(VERSION))
    print("=" * 60)
    for r in rows:
        print("{0} {1}:{2}".format(MARK[r["status"]], r["item"], r["value"]))
        if r["hint"] and r["status"] != OK:
            print("     → {0}".format(r["hint"]))
    print("=" * 60)
    if failed:
        print("結果：{0} 項需要先處理(❌)，處理完再執行一次。".format(len(failed)))
        return 1
    warns = len([r for r in rows if r["status"] == WARN])
    print("結果：可以開始。" + ("({0} 項提醒，不影響開始)".format(warns) if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
