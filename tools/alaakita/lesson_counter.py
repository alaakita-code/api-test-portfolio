#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlaAkita 重複錯誤計數器 lesson_counter.py v1.0

目的:同一類錯第二次出現,就自動列為晉升候選,不用等週五儀式。

journal 寫法(錯誤條目加標記,類別用英文小寫與連字號):
  - 知識庫 tbl() 收尾括號又寫錯 [錯誤:tbl-bracket]
  (全形「［錯誤：tbl-bracket］」也可以)

lessons.md 寫法(一行一條教訓):
  - L-20261115-01 類別:tbl-bracket 檢查:check_tbl_bracket — 說明
  - L-20261114-02 類別:sql-null-compare 檢查:tests/test_ingest.py::test_null_batch
  「檢查」可寫多個,以逗號分隔;
  只寫函式名 → 必須存在於 verify.py;寫「檔案::函式」→ 必須存在於該檔案。

判定:
  晉升候選  同類出現 ≥ 2 次,且 lessons.md 沒有對應的檢查        → 失敗
  復發      已晉升,但晉升日期之後又出現                        → 失敗(檢查沒擋住)
  假關閉    lessons.md 宣稱的檢查函式找不到                      → 失敗
  疑似同類  兩個標籤名稱很像(可能是同一類寫成兩種)              → 只提醒

用法:
  python3 lesson_counter.py --journal journal --lessons lessons.md
  python3 lesson_counter.py --journal journal --lessons lessons.md --list
  加 --warn-only:只報告不擋(exit 0)

exit code:0 沒有待處理 / 1 有晉升候選、復發或假關閉 / 2 呼叫錯誤
"""

import argparse
import difflib
import glob
import io
import os
import re
import sys

VERSION = "1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
TAG_RE = re.compile(u"[\\[［]錯誤[:：]\\s*([a-z0-9][a-z0-9-]*)\\s*[\\]］]")
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
HEADER_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})")
LID_RE = re.compile(r"L-(\d{4})(\d{2})(\d{2})")
CAT_RE = re.compile(u"類別\\s*[:：]\\s*([a-z0-9][a-z0-9-]*)")
CHK_RE = re.compile(u"檢查\\s*[:：]\\s*([^—\\n]+)")
SIMILAR = 0.85


class UsageError(Exception):
    pass


def _fix_console():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def read(path):
    with io.open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def collect_journal(journal):
    if os.path.isdir(journal):
        files = sorted(glob.glob(os.path.join(journal, "**", "*.md"), recursive=True))
    elif os.path.isfile(journal):
        files = [journal]
    else:
        raise UsageError("找不到 journal:{0}".format(journal))
    if not files:
        raise UsageError("journal 裡沒有任何 .md 檔")
    occ = {}  # tag -> list of (date or None, file, line_no, text)
    for path in files:
        m = DATE_RE.search(os.path.basename(path))
        current = "-".join(m.groups()) if m else None
        for no, line in enumerate(read(path).splitlines(), 1):
            h = HEADER_RE.match(line)
            if h:
                current = h.group(1)
                continue
            tags = set(TAG_RE.findall(line))  # 同一行同類只算一次
            for t in tags:
                occ.setdefault(t, []).append((current, os.path.basename(path), no, line.strip()))
    return occ


def resolve_check(spec, verify_py, root):
    """回傳 (存在與否, 說明)"""
    spec = spec.strip()
    if "::" in spec:
        rel, func = [x.strip() for x in spec.split("::", 1)]
        path = rel if os.path.isabs(rel) else os.path.join(root, rel)
    else:
        path, func = verify_py, spec
    if not os.path.isfile(path):
        return False, "找不到檔案 {0}".format(path)
    if not re.search(r"^\s*def\s+" + re.escape(func) + r"\s*\(", read(path), re.M):
        return False, "{0} 裡找不到 def {1}".format(os.path.basename(path), func)
    return True, ""


def collect_lessons(lessons, verify_py, root):
    """回傳 tag -> {'date', 'checks': [(spec, ok, why)], 'line'}"""
    out = {}
    if not lessons:
        return out
    if not os.path.isfile(lessons):
        raise UsageError("找不到 lessons:{0}".format(lessons))
    for no, line in enumerate(read(lessons).splitlines(), 1):
        c = CAT_RE.search(line)
        if not c:
            continue
        tag = c.group(1)
        lid = LID_RE.search(line)
        d = DATE_RE.search(line)
        date = "-".join(lid.groups()) if lid else ("-".join(d.groups()) if d else None)
        checks = []
        k = CHK_RE.search(line)
        if k:
            for spec in [x for x in re.split(u"[,，、]", k.group(1)) if x.strip()]:
                ok, why = resolve_check(spec.split()[0], verify_py, root)
                checks.append((spec.split()[0], ok, why))
        out[tag] = {"date": date, "checks": checks, "line": no}
    return out


def analyse(occ, lessons, threshold):
    findings = []  # (kind, tag, detail)
    for tag, items in sorted(occ.items()):
        les = lessons.get(tag)
        promoted = bool(les and les["checks"] and all(c[1] for c in les["checks"]))
        dates = [i[0] or "日期不明" for i in items]
        if les:
            for spec, ok, why in les["checks"]:
                if not ok:
                    findings.append(("假關閉", tag, "lessons.md 第 {0} 行宣稱的檢查 {1}:{2}".format(les["line"], spec, why)))
        if promoted and les["date"]:
            after = [i for i in items if i[0] and i[0] > les["date"]]
            if after:
                findings.append(("復發", tag, "{0} 已晉升,之後又出現 {1} 次:{2}".format(
                    les["date"], len(after), "、".join(i[0] for i in after))))
        if len(items) >= threshold and not promoted:
            why = "lessons.md 有記錄但沒有檢查" if les and not les["checks"] else (
                "lessons.md 沒有這一類" if not les else "檢查不存在")
            findings.append(("晉升候選", tag, "出現 {0} 次({1});{2}".format(
                len(items), "、".join(dates), why)))
    tags = sorted(occ)
    for i, a in enumerate(tags):
        for b in tags[i + 1:]:
            if difflib.SequenceMatcher(None, a, b).ratio() >= SIMILAR:
                findings.append(("疑似同類", a + " / " + b, "名稱很像,若是同一類請統一標籤,否則次數會被拆開"))
    return findings


def render(occ, findings, list_mode):
    blocking = [f for f in findings if f[0] != "疑似同類"]
    out = ["## AlaAkita 重複錯誤計數 v{0}:{1}".format(
        VERSION, "有待處理項目" if blocking else "沒有待處理項目"), ""]
    if findings:
        out += ["| 判定 | 類別 | 說明 |", "|---|---|---|"]
        for k, t, d in findings:
            out.append("| {0} | `{1}` | {2} |".format(k, t, d))
        out.append("")
    if list_mode or not findings:
        out += ["| 類別 | 次數 | 日期 |", "|---|---|---|"]
        for t, items in sorted(occ.items(), key=lambda x: (-len(x[1]), x[0])):
            out.append("| `{0}` | {1} | {2} |".format(t, len(items), "、".join(i[0] or "日期不明" for i in items)))
        if not occ:
            out.append("| (尚無任何 [錯誤:類別] 標記) | 0 | - |")
    return "\n".join(out) + "\n", bool(blocking)


def main(argv=None):
    _fix_console()
    p = argparse.ArgumentParser(description="AlaAkita 重複錯誤計數器")
    p.add_argument("--journal", required=True, help="journal 資料夾或單一檔案")
    p.add_argument("--lessons", default="", help="lessons.md 路徑")
    p.add_argument("--verify-py", default=os.path.join(HERE, "verify.py"))
    p.add_argument("--root", default=".", help="解析「檔案::函式」的根目錄")
    p.add_argument("--threshold", type=int, default=2)
    p.add_argument("--list", action="store_true", help="列出所有類別與次數")
    p.add_argument("--warn-only", action="store_true", help="只報告,不以 exit 1 擋下")
    a = p.parse_args(argv)
    try:
        occ = collect_journal(a.journal)
        les = collect_lessons(a.lessons, a.verify_py, os.path.abspath(a.root))
    except UsageError as e:
        print("[呼叫錯誤] {0}".format(e))
        return 2
    text, blocking = render(occ, analyse(occ, les, a.threshold), a.list)
    print(text)
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        with io.open(s, "a", encoding="utf-8") as f:
            f.write(text)
    return 1 if blocking and not a.warn_only else 0


if __name__ == "__main__":
    sys.exit(main())
