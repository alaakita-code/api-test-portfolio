#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlaAkita CI 擋關 gate.py v1.0 — 沒全綠就不能合併

在 GitHub Actions(或本機)依 .alaakita/gate.txt 依序執行:
  1. verify   :對指定的單檔 HTML 跑 verify.py(結果合不合格)
  2. path     :有比較基準時,跑 path_check.py(改動是否發生在預期位置)
  3. test     :執行專案自己的測試指令

設定檔 .alaakita/gate.txt(一行一條,# 為註解):
  verify  dist/*.html
  verify  tools/**/*.html
  test    python -m pytest -q
  expect  .alaakita/expect.txt      ← 可省略,預設就是這個

用法:
  python3 tools/alaakita/gate.py --base <比較基準 commit>   (CI 由工作流程帶入)
  python3 tools/alaakita/gate.py --base HEAD                (本機:比對尚未 commit 的改動)
  python3 tools/alaakita/gate.py                            (無基準:只跑 verify 與 test)

exit code:0 全綠 / 1 至少一項失敗 / 2 設定錯誤
擋關原則:
  - 設定檔沒有任何 verify 或 test → 視為設定錯誤,不給綠燈
  - verify 樣式找不到任何檔案   → 失敗(規則寫了卻沒檢查到東西)
  - 有基準但缺預期檔            → 失敗(無法證明改對地方)
"""

import argparse
import glob
import io
import os
import subprocess
import sys

VERSION = "1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
ZERO_SHA = "0" * 40


def _fix_console():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


class ConfigError(Exception):
    pass


def parse_config(path):
    if not os.path.isfile(path):
        raise ConfigError("找不到設定檔 {0}".format(path))
    cfg = {"verify": [], "test": [], "expect": ".alaakita/expect.txt"}
    with io.open(path, "r", encoding="utf-8-sig") as f:
        for no, line in enumerate(f.read().splitlines(), 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split(None, 1)
            if len(parts) != 2 or parts[0] not in ("verify", "test", "expect"):
                raise ConfigError("設定檔第 {0} 行無法辨識:{1}".format(no, s))
            key, val = parts[0], parts[1].strip()
            if key == "expect":
                cfg["expect"] = val
            else:
                cfg[key].append(val)
    if not cfg["verify"] and not cfg["test"]:
        raise ConfigError("設定檔沒有任何 verify 或 test。沒有檢查就不能給綠燈。")
    return cfg


def sh(cmd, cwd, shell=False):
    r = subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def tail(text, n=25):
    lines = text.rstrip().splitlines()
    return "\n".join(lines[-n:])


def run_gate(root, base, config_rel, verify_py, path_py):
    rows = []      # (類別, 項目, 狀態, 說明)
    logs = []      # (標題, 輸出)
    cfg = parse_config(os.path.join(root, config_rel))
    py = sys.executable

    # 1. verify
    for pat in cfg["verify"]:
        files = sorted(glob.glob(os.path.join(root, pat), recursive=True))
        files = [f for f in files if os.path.isfile(f)]
        if not files:
            rows.append(("verify", pat, "失敗", "樣式找不到任何檔案"))
            continue
        for f in files:
            rel = os.path.relpath(f, root).replace("\\", "/")
            code, out = sh([py, "-I", verify_py, f], root)
            rows.append(("verify", rel, "通過" if code == 0 else "失敗", "exit {0}".format(code)))
            if code != 0:
                logs.append(("verify " + rel, tail(out)))

    # 2. path_check
    if base and base != ZERO_SHA:
        exp = os.path.join(root, cfg["expect"])
        if not os.path.isfile(exp):
            rows.append(("path", cfg["expect"], "失敗", "有比較基準卻沒有預期檔,無法證明改對地方"))
        else:
            ok_base, _ = sh(["git", "rev-parse", "--verify", base + "^{commit}"], root)
            if ok_base != 0:
                rows.append(("path", base[:12], "失敗", "找不到比較基準 commit(checkout 需 fetch-depth: 0)"))
            else:
                code, out = sh([py, "-I", path_py, "--before-git", base, "--after", root,
                                "--expect", exp, "--ignore", ".alaakita/*"], root)
                rows.append(("path", "對照 " + base[:12], "通過" if code == 0 else "失敗",
                             "exit {0}".format(code)))
                if code != 0:
                    logs.append(("path_check", tail(out, 40)))
    else:
        rows.append(("path", "-", "略過", "沒有比較基準(排程、手動執行或新分支第一次推送)"))

    # 3. tests
    for cmd in cfg["test"]:
        code, out = sh(cmd, root, shell=True)
        rows.append(("test", cmd, "通過" if code == 0 else "失敗", "exit {0}".format(code)))
        if code != 0:
            logs.append(("test " + cmd, tail(out)))

    return rows, logs


def render(rows, logs, ok):
    md = ["## AlaAkita 擋關 v{0}:{1}".format(VERSION, "全綠,可以合併" if ok else "未全綠,禁止合併"), "",
          "| 類別 | 項目 | 狀態 | 說明 |", "|---|---|---|---|"]
    mark = {"通過": "✅ 通過", "失敗": "❌ 失敗", "略過": "⏭️ 略過"}
    for c, item, st, note in rows:
        md.append("| {0} | `{1}` | {2} | {3} |".format(c, item.replace("|", "\\|"), mark[st], note))
    for title, out in logs:
        md += ["", "<details><summary>{0} 的輸出</summary>".format(title), "", "```", out, "```", "</details>"]
    return "\n".join(md) + "\n"


def main(argv=None):
    _fix_console()
    p = argparse.ArgumentParser(description="AlaAkita CI 擋關")
    p.add_argument("--base", default="", help="比較基準 commit;空白代表沒有基準")
    p.add_argument("--root", default=".", help="專案根目錄,預設為目前資料夾")
    p.add_argument("--config", default=".alaakita/gate.txt")
    p.add_argument("--verify-py", default=os.path.join(HERE, "verify.py"))
    p.add_argument("--path-check-py", default=os.path.join(HERE, "path_check.py"))
    a = p.parse_args(argv)
    root = os.path.abspath(a.root)
    for label, f in (("verify.py", a.verify_py), ("path_check.py", a.path_check_py)):
        if not os.path.isfile(f):
            print("[設定錯誤] 找不到 {0}:{1}".format(label, f))
            return 2
    try:
        rows, logs = run_gate(root, a.base.strip(), a.config, a.verify_py, a.path_check_py)
    except ConfigError as e:
        print("[設定錯誤] {0}".format(e))
        return 2
    ok = all(r[2] != "失敗" for r in rows) and any(r[2] == "通過" for r in rows)
    text = render(rows, logs, ok)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with io.open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
