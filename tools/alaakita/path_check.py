#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alaakita-verify 路徑檢查器 path_check.py v1.2

目的:攔下「看起來全綠,其實沒改到該改的地方」。
verify.py 檢查「結果合不合格」,本檔檢查「修改是不是真的發生在預期的位置」。

真實事故(本檔的陷阱測試逐一重現):
  1. 知識庫 v3.7:寫入腳本中途失敗、檔案根本沒被改,verify 仍 8/8 全綠。
  2. OSS Alarm:改的是不會執行的 functions/,部署成功、版本號也更新了。
  3. 標記在修改前就已存在 → 只檢查「有出現」會誤判通過。

用法:
  python3 path_check.py --before 舊檔 --after 新檔 --expect 預期.txt
  python3 path_check.py --before 舊資料夾 --after 新資料夾 --expect 預期.txt
  python3 path_check.py --before-git HEAD --after 專案資料夾 --expect 預期.txt
  python3 path_check.py --before 舊檔 --after https://網址 --expect 預期.txt
  加上 --ignore ".alaakita/*" 可排除不算「真正改動」的檔案(可重複指定)

預期檔格式(UTF-8,一行一條,# 開頭為註解):
  + 標記            修改後出現次數必須「多於」修改前
  - 標記            修改前存在,修改後必須為 0
  = 標記            修改前後都必須存在(不可誤刪)
資料夾/git 模式要指定檔案:
  + src/index.js :: handleUpdateIncidentStatus

exit code:0 全部通過 / 1 至少一項失敗 / 2 呼叫或預期檔錯誤
"""

import argparse
import fnmatch
import hashlib
import io
import os
import subprocess
import sys

VERSION = "1.2"
SEP = " :: "
DEFAULT_SHRINK = 0.5  # 新版小於舊版 50% 視為異常縮水(P-02)


class UsageError(Exception):
    pass


def _fix_console():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def parse_manifest(path):
    if not os.path.isfile(path):
        raise UsageError("找不到預期檔:{0}".format(path))
    with io.open(path, "r", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    rules = []
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        op = s[0]
        if op not in "+-=" or len(s) < 3 or s[1] != " ":
            raise UsageError("預期檔第 {0} 行格式錯誤(開頭須為「+ 」「- 」「= 」):{1}".format(no, s))
        body = s[2:].strip()
        target = None
        if SEP in body:
            target, body = body.split(SEP, 1)
            target = target.strip().replace("\\", "/")
            body = body.strip()
        if not body:
            raise UsageError("預期檔第 {0} 行沒有標記內容".format(no))
        rules.append({"line": no, "op": op, "file": target, "token": body})
    if not rules:
        raise UsageError("預期檔沒有任何規則。沒有預期就無法證明改對地方,拒絕判定通過。")
    return rules


# ---------- 讀取來源 ----------

def is_url(s):
    return s.startswith("http://") or s.startswith("https://")


def fetch_url(url):
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except Exception as e:
        raise UsageError("無法讀取網址 {0}:{1}".format(url, e))


SKIP_DIRS = (".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache")


def list_tree(root):
    """git repo:只列「已追蹤＋未追蹤但沒被 .gitignore 排除」的檔案(v1.2)。
    不是 git repo:走訪資料夾,略過 SKIP_DIRS。"""
    r = subprocess.run(["git", "-C", root, "ls-files", "-co", "--exclude-standard", "-z"],
                       capture_output=True)
    top = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if r.returncode == 0 and top.returncode == 0 and \
            os.path.normcase(os.path.abspath(top.stdout.strip())) == os.path.normcase(os.path.abspath(root)):
        rels = [x.decode("utf-8", "replace") for x in r.stdout.split(b"\0") if x]
        return sorted(set(x for x in rels if os.path.isfile(os.path.join(root, x))))
    rels = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for fn in files:
            rels.append(os.path.relpath(os.path.join(d, fn), root).replace("\\", "/"))
    return sorted(rels)


def read_tree(root):
    out = {}
    for rel in list_tree(root):
        with open(os.path.join(root, rel), "rb") as f:
            out[rel] = f.read()
    return out


def git_show(repo, rev, rel):
    r = subprocess.run(["git", "-C", repo, "show", "{0}:{1}".format(rev, rel)],
                       capture_output=True)
    if r.returncode != 0:
        return None  # 該版本沒有這個檔案 → 視為不存在
    return r.stdout


def load_side(spec, rules, label):
    """回傳 ('single', bytes) 或 ('tree', {相對路徑: bytes})"""
    if is_url(spec):
        return "single", fetch_url(spec)
    if os.path.isfile(spec):
        with open(spec, "rb") as f:
            return "single", f.read()
    if os.path.isdir(spec):
        return "tree", read_tree(spec)
    raise UsageError("找不到{0}:{1}".format(label, spec))


# ---------- 檢查 ----------

class Report(object):
    def __init__(self):
        self.items = []

    def add(self, name, ok, detail=""):
        self.items.append((name, ok, detail))

    def passed(self):
        return all(i[1] for i in self.items)

    def text(self):
        out = ["=" * 60, "AlaAkita 路徑檢查 v{0}".format(VERSION), "=" * 60]
        for name, ok, detail in self.items:
            out.append("[{0}] {1}".format("✅ 通過" if ok else "❌ 失敗", name))
            if detail:
                out.append("       -> {0}".format(detail))
        ok_n = sum(1 for i in self.items if i[1])
        out.append("-" * 60)
        out.append("結果:{0}/{1} 項通過".format(ok_n, len(self.items)))
        out.append("狀態:" + ("修改確實發生在預期位置。" if self.passed()
                             else "修改未被證明,禁止宣稱完成。"))
        out.append("=" * 60)
        return "\n".join(out)


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def run(args):
    rules = parse_manifest(args.expect)
    rep = Report()

    if args.before_git:
        if not os.path.isdir(args.after):
            raise UsageError("--before-git 模式下 --after 必須是專案資料夾")
        a_kind, after = load_side(args.after, rules, "修改後")
        before = {}
        for rel in set(list(after.keys()) + [r["file"] for r in rules if r["file"]]):
            b = git_show(args.after, args.before_git, rel)
            if b is not None:
                before[rel] = b
        b_kind = "tree"
    else:
        b_kind, before = load_side(args.before, rules, "修改前")
        a_kind, after = load_side(args.after, rules, "修改後")

    if b_kind != a_kind:
        raise UsageError("修改前與修改後的類型不同(一個是檔案、一個是資料夾)")

    # 1. 有沒有真的改
    if a_kind == "single":
        changed = before != after
        rep.add("內容確實有變動", changed,
                "修改前後完全相同(sha {0}),可能寫入失敗或改到別的檔案".format(sha(after))
                if not changed else "sha {0} → {1}".format(sha(before), sha(after)))
    else:
        diff = sorted(k for k in set(before) | set(after)
                      if before.get(k) != after.get(k)
                      and not any(fnmatch.fnmatch(k, pat) for pat in args.ignore))
        rep.add("內容確實有變動", bool(diff),
                "變動檔案:" + "、".join(diff[:8]) + (" 等 {0} 個".format(len(diff)) if len(diff) > 8 else "")
                if diff else "沒有任何檔案變動")

    # 2. 縮水檢查(P-02)
    if a_kind == "single":
        bs, as_ = len(before), len(after)
        if bs == 0:
            rep.add("大小檢查(P-02)", as_ > 0, "新版 {0} bytes".format(as_))
        else:
            ratio = float(as_) / bs
            rep.add("大小檢查(P-02)", ratio >= args.shrink,
                    "新版是舊版的 {0:.0%}({1} → {2} bytes)".format(ratio, bs, as_))
    else:
        bad = []
        for k in after:
            if k in before and len(before[k]) > 0 and float(len(after[k])) / len(before[k]) < args.shrink:
                bad.append("{0}({1:.0%})".format(k, float(len(after[k])) / len(before[k])))
        rep.add("大小檢查(P-02)", not bad, "異常縮水:" + "、".join(bad) if bad else "無檔案異常縮水")

    # 3. 逐條預期
    for r in rules:
        if a_kind == "single":
            if r["file"]:
                raise UsageError("預期檔第 {0} 行指定了檔案,但比對對象是單一檔案".format(r["line"]))
            b_txt, a_txt, where = decode(before), decode(after), ""
        else:
            if not r["file"]:
                raise UsageError("資料夾模式下,預期檔第 {0} 行必須用「檔案 :: 標記」指定檔案".format(r["line"]))
            if r["file"] not in after and r["op"] != "-":
                rep.add("第 {0} 行 {1} {2}".format(r["line"], r["op"], r["token"]), False,
                        "修改後找不到檔案 {0}".format(r["file"]))
                continue
            b_txt = decode(before.get(r["file"], b""))
            a_txt = decode(after.get(r["file"], b""))
            where = r["file"] + SEP
        bc, ac = b_txt.count(r["token"]), a_txt.count(r["token"])
        name = "第 {0} 行 {1} {2}{3}".format(r["line"], r["op"], where, r["token"])
        if r["op"] == "+":
            ok = ac > bc
            detail = "次數 {0} → {1}".format(bc, ac)
            if not ok and bc > 0:
                detail += "(修改前就已存在,次數沒有增加,不能當成新改動的證據)"
        elif r["op"] == "-":
            ok = bc > 0 and ac == 0
            detail = "次數 {0} → {1}".format(bc, ac)
            if bc == 0:
                detail += "(修改前就不存在,這條規則無法證明任何事)"
        else:
            ok = bc > 0 and ac > 0
            detail = "次數 {0} → {1}".format(bc, ac)
        rep.add(name, ok, detail)

    return rep


def main(argv=None):
    _fix_console()
    p = argparse.ArgumentParser(description="AlaAkita 路徑檢查:證明修改真的發生在預期位置")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--before", help="修改前的檔案、資料夾或網址")
    g.add_argument("--before-git", help="用 git 版本當修改前(例如 HEAD)")
    p.add_argument("--after", required=True, help="修改後的檔案、資料夾或網址")
    p.add_argument("--expect", required=True, help="預期檔")
    p.add_argument("--ignore", action="append", default=[],
                   help="資料夾模式下,不算進「內容確實有變動」的檔案樣式,可重複指定")
    p.add_argument("--shrink", type=float, default=DEFAULT_SHRINK, help="縮水門檻,預設 0.5")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        rep = run(args)
    except UsageError as e:
        print("[呼叫錯誤] {0}".format(e))
        return 2
    print(rep.text())
    return 0 if rep.passed() else 1


if __name__ == "__main__":
    sys.exit(main())
