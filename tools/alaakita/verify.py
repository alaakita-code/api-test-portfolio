#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alaakita-verify — AlaAkita 單檔 HTML 工具交付前驗收器

用法:
    python3 verify.py <path/to/tool.html>

原則(對應 journal 2026-07-09 F-001):
    規則放在程式碼裡,不放在散文裡。
    exit code 0 = 全綠,可以說「完成」。
    exit code 非 0 = 至少一項失敗,不得宣稱完成。

六項檢查(依 D-004 健檢結論):
    1. BOM 檢查
    2. node --check(JS 語法)
    3. ES5-only 掃描(禁 arrow function / template literal / let·const / optional chaining)
    4. 簡體字掃描
    5. div onclick 稽核(Android content:// 相容性)
    6. <script> 標籤配對檢查

教訓晉升規則(G-02):
    lessons.md 每新增一條教訓,必須同時在本檔新增一項對應檢查,
    否則該教訓不准標記為「已關閉」。
"""

import sys
import re
import os
import subprocess
import unicodedata


class VerifyResult(object):
    def __init__(self):
        self.checks = []  # list of (name, passed(bool), detail(str))

    def add(self, name, passed, detail=""):
        self.checks.append((name, passed, detail))

    def all_passed(self):
        return all(c[1] for c in self.checks)

    def report(self):
        lines = []
        lines.append("=" * 60)
        lines.append("AlaAkita Verify 報告")
        lines.append("=" * 60)
        for name, passed, detail in self.checks:
            mark = "✅ 通過" if passed else "❌ 失敗"
            lines.append("[{0}] {1}".format(mark, name))
            if detail and not passed:
                lines.append("       -> {0}".format(detail))
        lines.append("-" * 60)
        total = len(self.checks)
        ok = sum(1 for c in self.checks if c[1])
        lines.append("結果: {0}/{1} 項通過".format(ok, total))
        if self.all_passed():
            lines.append("狀態: 全綠,可以宣稱完成。")
        else:
            lines.append("狀態: 未全綠,禁止宣稱完成。")
        lines.append("=" * 60)
        return "\n".join(lines)


def check_bom(content_bytes, result):
    """檢查 1: BOM 檢查 — 必須以 UTF-8 BOM 開頭"""
    has_bom = content_bytes[:3] == b'\xef\xbb\xbf'
    result.add(
        "BOM 檢查(UTF-8 with BOM)",
        has_bom,
        "檔案開頭缺少 EF BB BF,Android content:// 開啟時可能出現編碼問題" if not has_bom else ""
    )
    return has_bom


def extract_scripts(text):
    """從 HTML 中取出所有 <script>...</script> 內容(排除有 src 的外部腳本標籤)"""
    scripts = []
    for m in re.finditer(r'<script(\s[^>]*)?>(.*?)</script>', text, re.DOTALL | re.IGNORECASE):
        attrs = m.group(1) or ""
        if 'src=' in attrs.lower():
            continue
        scripts.append(m.group(2))
    return scripts


def check_node_syntax(text, result):
    """檢查 2: node --check — JS 語法必須合法"""
    scripts = extract_scripts(text)
    if not scripts:
        result.add("node --check(JS 語法)", False, "找不到任何內嵌 <script> 區塊")
        return False

    combined = "\n;\n".join(scripts)
    tmp_path = "/tmp/_alaakita_verify_check.js"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(combined)
    except Exception as e:
        result.add("node --check(JS 語法)", False, "寫入暫存檔失敗: {0}".format(e))
        return False

    try:
        r = subprocess.run(
            ["node", "--check", tmp_path],
            capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        result.add("node --check(JS 語法)", False, "找不到 node 執行檔,無法驗證語法")
        return False
    except Exception as e:
        result.add("node --check(JS 語法)", False, "執行失敗: {0}".format(e))
        return False

    passed = (r.returncode == 0)
    detail = r.stderr.strip()[:300] if not passed else ""
    result.add("node --check(JS 語法)", passed, detail)
    return passed


ES5_VIOLATIONS = [
    (r'=>', "箭頭函式(arrow function)"),
    (r'`', "模板字面量(template literal / 反引號)"),
    (r'\blet\s+\w', "let 宣告"),
    (r'\bconst\s+\w', "const 宣告"),
    (r'\?\.', "optional chaining(?.)"),
    (r'\.\.\.\w', "spread/rest 運算子(...)"),
    (r'\bclass\s+\w+\s*\{', "class 語法"),
]


def check_es5_only(text, result):
    """檢查 3: ES5-only 掃描 — 禁止 ES6+ 語法"""
    scripts = extract_scripts(text)
    combined = "\n".join(scripts)
    # 先移除字串與註解,降低誤判(簡化版,非完整 tokenizer)
    no_comments = re.sub(r'//.*', '', combined)
    no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)
    no_strings = re.sub(r"'(?:\\.|[^'\\])*'", "''", no_comments)
    no_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', no_strings)
    # 剝除正則字面量:反引號常合法出現在 /^```/ 這類 regex 中,不剝除會誤報模板字面量
    no_comments = re.sub(
        r'/(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[])+/[gimsuy]*',
        'RE', no_strings
    )

    found = []
    for pattern, label in ES5_VIOLATIONS:
        matches = re.findall(pattern, no_comments)
        if matches:
            found.append("{0} x{1}".format(label, len(matches)))

    passed = len(found) == 0
    result.add(
        "ES5-only 掃描",
        passed,
        "偵測到非 ES5 語法: " + "; ".join(found) if not passed else ""
    )
    return passed


def _load_simplified_char_set():
    """
    取得簡體字集合。
    優先順序:
      1. references/simplified_chars.txt(完整字表,若存在)
      2. 內建高頻字表(備援,覆蓋率有限,僅作最後防線)
    """
    here = os.path.dirname(os.path.abspath(__file__))
    table_path = os.path.join(here, "references", "simplified_chars.txt")
    if os.path.isfile(table_path):
        with open(table_path, "r", encoding="utf-8") as f:
            chars = f.read().strip()
        if chars:
            return set(chars), "完整字表"

    fallback = (
        "国学习为对时问题这与业务体现产实现应该"
        "计划过后来说没关系还没经济发电脑软件网络"
        "数据处理专业管理组织结构设计开发运行环境"
        "系统资源报告标准执行确认删除编辑显示隐藏"
        "内页导航链接图标颜色边框圆角阴影渐变动画"
        "换转变简单启动关闭连结"
    )
    return set(fallback), "備援字表(覆蓋率有限)"


def check_simplified_chinese(text, result):
    """檢查 4: 簡體字掃描 — 內文不得含簡體字"""
    simplified_chars, source_label = _load_simplified_char_set()
    text_no_tag = re.sub(r'<[^>]*>', '', text)
    found_chars = set()
    for ch in text_no_tag:
        if ch in simplified_chars:
            found_chars.add(ch)

    passed = len(found_chars) == 0
    detail = ""
    if not passed:
        sample = "".join(sorted(found_chars))[:20]
        detail = "疑似簡體字: {0}(共 {1} 種,來源:{2},請人工複查是否為誤判)".format(
            sample, len(found_chars), source_label
        )
    result.add("簡體字掃描({0})".format(source_label), passed, detail)
    return passed


def check_div_onclick(text, result):
    """檢查 5: div onclick 稽核 — 禁止 <div onclick=...this...>(content:// 下 this 指向 window)"""
    violations = []
    for m in re.finditer(r'<div\b[^>]*\bonclick\s*=\s*["\']([^"\']*)["\']', text, re.IGNORECASE):
        onclick_content = m.group(1)
        if re.search(r'\bthis\b', onclick_content):
            violations.append(onclick_content[:60])

    # 額外檢查: onclick 與 ontouchend 同時存在(雙重執行風險)
    double_fire = re.findall(
        r'<(?:button|div)\b[^>]*\bonclick\s*=\s*["\'][^"\']*["\'][^>]*\bontouchend\s*=',
        text, re.IGNORECASE
    )

    passed = (len(violations) == 0) and (len(double_fire) == 0)
    detail_parts = []
    if violations:
        detail_parts.append("div onclick 含 this: {0} 處".format(len(violations)))
    if double_fire:
        detail_parts.append("onclick+ontouchend 同時存在: {0} 處(雙重觸發風險)".format(len(double_fire)))
    result.add("div onclick 稽核(Android content:// 相容)", passed, "; ".join(detail_parts))
    return passed


def check_script_tag_pairing(text, result):
    """檢查 6: <script> 標籤配對檢查"""
    opens = len(re.findall(r'<script(?:\s[^>]*)?>', text, re.IGNORECASE))
    closes = len(re.findall(r'</script\s*>', text, re.IGNORECASE))
    passed = (opens == closes) and (opens > 0)
    detail = ""
    if not passed:
        if opens == 0:
            detail = "找不到任何 <script> 標籤"
        else:
            detail = "開始標籤 {0} 個,結束標籤 {1} 個,數量不一致".format(opens, closes)
    result.add("<script> 標籤配對", passed, detail)
    return passed


def check_div_balance(text, result):
    """加碼檢查: <div> 開合配對(常見遺漏 </div> 導致後續 tab 全部消失,見歷史事故)"""
    opens = len(re.findall(r'<div\b[^>]*(?<!/)>', text, re.IGNORECASE))
    closes = len(re.findall(r'</div\s*>', text, re.IGNORECASE))
    self_closed = len(re.findall(r'<div\b[^>]*/>', text, re.IGNORECASE))
    opens -= self_closed
    passed = (opens == closes)
    detail = ""
    if not passed:
        detail = "<div> 開 {0} 個, </div> 關 {1} 個,差 {2} 個(常見於遺漏收尾,導致後續 tab 內容被吞掉)".format(
            opens, closes, opens - closes
        )
    result.add("<div> 開合配對(加碼)", passed, detail)
    return passed


def main():
    if len(sys.argv) < 2:
        print("用法: python3 verify.py <path/to/tool.html>")
        sys.exit(2)

    path = sys.argv[1]
    if not os.path.isfile(path):
        print("找不到檔案: {0}".format(path))
        sys.exit(2)

    with open(path, "rb") as f:
        raw = f.read()

    # 檔案大小異常檢查(對應 P-02 熔斷條款: 0 bytes 或明顯縮水)
    size = len(raw)

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        print("檔案無法以 UTF-8 解碼,請先確認編碼。")
        sys.exit(2)

    result = VerifyResult()

    if size == 0:
        result.add("檔案大小檢查(P-02 熔斷)", False, "檔案為 0 bytes")
    else:
        result.add("檔案大小檢查(P-02 熔斷)", True, "{0} bytes".format(size))

    check_bom(raw, result)
    check_script_tag_pairing(text, result)
    check_div_balance(text, result)
    check_node_syntax(text, result)
    check_es5_only(text, result)
    check_simplified_chinese(text, result)
    check_div_onclick(text, result)

    print(result.report())

    sys.exit(0 if result.all_passed() else 1)


if __name__ == "__main__":
    main()
