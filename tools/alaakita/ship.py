#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlaAkita 改動流程自動化 ship.py v1.0

人工只留兩個點:改之前寫好預期(.alaakita/expect.txt)、合併前看 PR 內容。
其餘步驟自動執行。

用法(在 repo 根目錄):
  python tools/alaakita/ship.py start  分支名稱
      從最新 main 開分支,建立預期檔範本
  python tools/alaakita/ship.py submit "commit 訊息"
      本機擋關 → commit → push → 開 PR → 等所有檢查跑完
      全綠:印出 PR 網址後停下,等你在 GitHub 看內容、按合併
  python tools/alaakita/ship.py finish
      確認 PR 已合併 → 切回 main、pull、刪除分支

刻意不做的事:
  - 不自動合併(合併一定由人在 GitHub 上按)
  - 本機擋關沒過就不 commit、不推送
  - 檢查沒有出現、逾時、缺少必要檢查,一律不算通過

必要檢查清單(可選):.alaakita/required_checks.txt,一行一個檢查名稱
需要 GitHub CLI(gh):winget install --id GitHub.cli -e,再執行 gh auth login

exit code:0 成功 / 1 檢查失敗或條件不符 / 2 環境或呼叫錯誤
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

VERSION = "1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
EXPECT = ".alaakita/expect.txt"
REQUIRED = ".alaakita/required_checks.txt"
TEMPLATE = u"""# 這次改動的預期(先寫這裡,再改內容)
# + 檔案 :: 標記   修改後次數必須比修改前多
# - 檔案 :: 標記   修改前存在、修改後必須為 0
# = 檔案 :: 標記   修改前後都必須存在(防誤刪)
#
# 例:
# + README.md :: 新增的那句話
# = pytest.ini :: testpaths = tests
#
# 本檔沒有任何規則時,submit 會被擋下。
"""


class Stop(Exception):
    def __init__(self, msg, code=1):
        Exception.__init__(self, msg)
        self.code = code


def _fix_console():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def say(msg):
    print(msg)
    sys.stdout.flush()


def run(cmd, check=True, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise Stop("指令失敗:{0}\n{1}".format(" ".join(cmd), (r.stdout + r.stderr).strip()), 1)
    return r


def git(*args, **kw):
    return run(["git"] + list(args), **kw)


def gh_cmd():
    custom = os.environ.get("SHIP_GH")
    if custom:
        return [sys.executable, custom] if custom.endswith(".py") else [custom]
    found = shutil.which("gh")
    if not found:
        raise Stop("找不到 GitHub CLI(gh)。請先執行:winget install --id GitHub.cli -e,"
                   "關掉 PowerShell 重開後再執行:gh auth login", 2)
    return [found]


def gh(*args, **kw):
    return run(gh_cmd() + list(args), **kw)


def repo_root():
    r = git("rev-parse", "--show-toplevel", check=False)
    if r.returncode != 0:
        raise Stop("目前不在 git repo 裡", 2)
    root = r.stdout.strip()
    if not os.path.isfile(os.path.join(root, ".alaakita", "gate.txt")):
        raise Stop("這個 repo 沒有 .alaakita/gate.txt,請先安裝擋關包", 2)
    return root


def current_branch():
    return git("branch", "--show-current").stdout.strip()


def ensure_clean():
    out = git("status", "--porcelain").stdout.strip()
    if out:
        raise Stop("還有尚未 commit 的修改,請先處理:\n" + out, 1)


# ---------------- start ----------------

def cmd_start(name):
    root = repo_root()
    os.chdir(root)
    if not name or name in ("main", "master"):
        raise Stop("請給一個新的分支名稱,例如:docs/update-readme", 2)
    ensure_clean()
    git("switch", "main")
    git("pull", "--ff-only")
    if git("rev-parse", "--verify", "refs/heads/" + name, check=False).returncode == 0:
        raise Stop("分支 {0} 已經存在".format(name), 1)
    git("switch", "-c", name)
    with io.open(EXPECT, "w", encoding="utf-8", newline="") as f:
        f.write(TEMPLATE)
    say("已從最新 main 建立分支:{0}".format(name))
    say("下一步:")
    say("  1. 先在 {0} 寫下這次的預期".format(EXPECT))
    say("  2. 修改內容")
    say('  3. python tools/alaakita/ship.py submit "commit 訊息"')
    return 0


# ---------------- submit ----------------

def read_required():
    if not os.path.isfile(REQUIRED):
        return []
    with io.open(REQUIRED, encoding="utf-8-sig") as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]


def local_gate(base):
    r = run([sys.executable, "-I", os.path.join(HERE, "gate.py"), "--base", base], check=False)
    return r.returncode, r.stdout + r.stderr


def find_pr(branch):
    r = gh("pr", "view", branch, "--json", "url,state", check=False)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def poll_checks(branch, required, timeout, interval):
    """回傳 (是否全過, 說明列)。沒出現、逾時、缺必要檢查都算不過。"""
    deadline = time.time() + timeout
    last = []
    while True:
        r = gh("pr", "checks", branch, "--json", "name,bucket,link", check=False)
        checks = None
        try:
            checks = json.loads(r.stdout) if r.stdout.strip() else None
        except ValueError:
            checks = None
        if checks:
            last = checks
            pending = [c for c in checks if c.get("bucket") == "pending"]
            names = set(c.get("name") for c in checks)
            missing = [n for n in required if n not in names]
            if not pending and not missing:
                failed = [c for c in checks if c.get("bucket") not in ("pass", "skipping")]
                req_bad = [c for c in checks if c.get("name") in required and c.get("bucket") != "pass"]
                lines = ["  {0} {1}".format("✅" if c.get("bucket") == "pass" else
                                            ("⏭️" if c.get("bucket") == "skipping" else "❌"),
                                            c.get("name")) for c in checks]
                for c in failed + req_bad:
                    if c.get("link"):
                        lines.append("  失敗詳情:{0} → {1}".format(c.get("name"), c.get("link")))
                return (not failed and not req_bad), lines
        if time.time() >= deadline:
            if not last:
                return False, ["  逾時:等不到任何檢查出現(檢查沒跑,不能算通過)"]
            names = set(c.get("name") for c in last)
            lines = ["  逾時:仍有檢查未完成或缺少必要檢查"]
            lines += ["  缺少必要檢查:{0}".format(n) for n in required if n not in names]
            lines += ["  {0}:{1}".format(c.get("name"), c.get("bucket")) for c in last]
            return False, lines
        time.sleep(interval)


def cmd_submit(message):
    root = repo_root()
    os.chdir(root)
    if not message:
        raise Stop('請提供 commit 訊息,例如:ship.py submit "Update README"', 2)
    branch = current_branch()
    if branch in ("main", "master", ""):
        raise Stop("目前在 {0},請先用 ship.py start 開分支".format(branch or "detached HEAD"), 1)
    gh_cmd()  # 先確認 gh 存在,避免 commit 後才發現推不上去

    base = git("merge-base", "main", "HEAD").stdout.strip()
    say("[1/4] 本機擋關(對照 main 分岔點 {0})".format(base[:12]))
    code, out = local_gate(base)
    if code != 0:
        say(out)
        raise Stop("本機擋關沒過,沒有 commit、沒有推送。修正後再執行 submit。", 1)
    say("      通過")

    say("[2/4] commit 並推送")
    git("add", "-A")
    staged = git("diff", "--cached", "--name-only").stdout.split()
    if staged:
        git("commit", "-m", message)
        say("      commit:{0} 個檔案".format(len(staged)))
    else:
        say("      沒有新的修改,沿用既有 commit")
    git("push", "-u", "origin", branch)

    say("[3/4] 建立或更新 PR")
    pr = find_pr(branch)
    if pr and pr.get("state") == "OPEN":
        say("      沿用既有 PR:{0}".format(pr.get("url")))
    else:
        with io.open(EXPECT, encoding="utf-8-sig") as f:
            expect = f.read()
        body = u"## Expected changes\n\n```\n{0}\n```\n\nLocal AlaAkita Gate: passed\n".format(expect.strip())
        fd, path = tempfile.mkstemp(suffix=".md")
        with io.open(fd, "w", encoding="utf-8") as f:
            f.write(body)
        try:
            gh("pr", "create", "--base", "main", "--head", branch, "--title", message, "--body-file", path)
        finally:
            os.remove(path)
        pr = find_pr(branch) or {}
        say("      已建立:{0}".format(pr.get("url", "(網址待確認)")))

    say("[4/4] 等待 GitHub 檢查")
    timeout = float(os.environ.get("SHIP_TIMEOUT_SECONDS", "900"))
    interval = float(os.environ.get("SHIP_POLL_SECONDS", "15"))
    ok, lines = poll_checks(branch, read_required(), timeout, interval)
    for l in lines:
        say(l)
    if not ok:
        raise Stop("檢查沒有全綠,不能合併。修正後再執行一次 submit。", 1)
    say("")
    say("全部通過。請到 GitHub 看 Files changed,內容正確再按 Merge pull request:")
    say("  {0}".format(pr.get("url", "")))
    say("合併後執行:python tools/alaakita/ship.py finish")
    return 0


# ---------------- finish ----------------

def cmd_finish():
    root = repo_root()
    os.chdir(root)
    branch = current_branch()
    if branch in ("main", "master", ""):
        raise Stop("目前不在功能分支上,沒有要收尾的 PR", 1)
    ensure_clean()
    pr = find_pr(branch)
    if not pr:
        raise Stop("找不到分支 {0} 的 PR".format(branch), 1)
    if pr.get("state") != "MERGED":
        raise Stop("PR 還沒合併(目前狀態:{0})。請先到 GitHub 看內容並合併:{1}".format(
            pr.get("state"), pr.get("url")), 1)
    git("switch", "main")
    git("pull", "--ff-only")
    if git("branch", "-d", branch, check=False).returncode != 0:
        git("branch", "-D", branch)  # squash／rebase 合併時本地看不出已合併;PR 已確認 MERGED
    if git("ls-remote", "--exit-code", "--heads", "origin", branch, check=False).returncode == 0:
        git("push", "origin", "--delete", branch)
    git("fetch", "--prune", check=False)
    say("已收尾:回到 main 並同步,分支 {0} 已刪除。".format(branch))
    return 0


def main(argv=None):
    _fix_console()
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("start", "submit", "finish"):
        say(__doc__)
        return 2
    try:
        if argv[0] == "start":
            return cmd_start(argv[1] if len(argv) > 1 else "")
        if argv[0] == "submit":
            return cmd_submit(" ".join(argv[1:]).strip())
        return cmd_finish()
    except Stop as e:
        say("[停止] {0}".format(e))
        return e.code


if __name__ == "__main__":
    sys.exit(main())
