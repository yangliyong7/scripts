#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 vocab/review.xlsx 的各 sheet A 列读取单词，覆盖写入
vocab/spelling-trainer.html 里的 REVIEW_WORDS 数组。

用法:
    python3 tools/sync_review_words.py            # 同步（有变化才写文件）
    python3 tools/sync_review_words.py --check    # 只检查，有差异退出码 1
    python3 tools/sync_review_words.py --dry-run  # 打印将要写入的内容，不改文件

设计要点:
- 释义不在这里处理：页面运行时用 defOf() 去 DATA(data.json) 里查，保持原有取法。
- 只替换 `var REVIEW_WORDS = [...];` 这一行，不触碰其它逻辑。
- 单词按 Excel 中出现的先后顺序保留，大小写按 Excel 原样，按小写去重。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
XLSX = os.path.join(ROOT, "vocab", "review.xlsx")
HTML = os.path.join(ROOT, "vocab", "spelling-trainer.html")

REVIEW_LINE = re.compile(r"^var REVIEW_WORDS = \[.*?\];$", re.MULTILINE | re.DOTALL)


def read_words(path):
    """读取 xlsx 所有 sheet 的 A 列，返回去重后的单词列表（保持出现顺序）。"""
    try:
        import openpyxl
    except ImportError:
        sys.exit("缺少 openpyxl，请先安装: pip install openpyxl")

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    words, seen = [], set()
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_col=1, max_col=1, values_only=True):
            cell = row[0] if row else None
            if cell is None:
                continue
            w = str(cell).strip()
            if not w:
                continue
            key = w.lower()
            if key in seen:
                continue
            seen.add(key)
            words.append(w)
    wb.close()
    return words


def build_line(words):
    js = json.dumps(words, ensure_ascii=False, separators=(",", ":"))
    return "var REVIEW_WORDS = " + js + ";"


def main():
    check_only = "--check" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if not os.path.exists(XLSX):
        sys.exit("找不到 Excel: " + XLSX)
    if not os.path.exists(HTML):
        sys.exit("找不到 HTML: " + HTML)

    words = read_words(XLSX)
    if not words:
        sys.exit("Excel A 列没读到任何单词，中止（避免把词表清空）")

    new_line = build_line(words)

    with open(HTML, encoding="utf-8") as f:
        html = f.read()

    m = REVIEW_LINE.search(html)
    if not m:
        sys.exit("HTML 里找不到 `var REVIEW_WORDS = [...];` 这一行，无法自动同步")

    old_line = m.group(0)
    if old_line == new_line:
        print("[sync] 词表已是最新，无需改动（%d 词）" % len(words))
        return 0

    # 解析旧词表，报告差异
    try:
        old_words = json.loads(old_line[len("var REVIEW_WORDS = "):-1])
    except Exception:
        old_words = []
    old_set, new_set = {w.lower() for w in old_words}, {w.lower() for w in words}
    added = [w for w in words if w.lower() not in old_set]
    removed = [w for w in old_words if w.lower() not in new_set]

    print("[sync] Excel: %d 词 | HTML 原有: %d 词" % (len(words), len(old_words)))
    if added:
        print("[sync] 新增 %d: %s" % (len(added), ", ".join(added[:15]) + (" ..." if len(added) > 15 else "")))
    if removed:
        print("[sync] 移除 %d: %s" % (len(removed), ", ".join(removed[:15]) + (" ..." if len(removed) > 15 else "")))

    if check_only:
        print("[sync] --check: 词表有差异，需要同步")
        return 1

    if dry_run:
        print("[sync] --dry-run: 将写入:")
        print(new_line[:400] + (" ..." if len(new_line) > 400 else ""))
        return 0

    html = html[:m.start()] + new_line + html[m.end():]
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("[sync] 已覆盖写入 REVIEW_WORDS -> %s" % HTML)
    return 0


if __name__ == "__main__":
    sys.exit(main())
