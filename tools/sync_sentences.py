#!/usr/bin/env python3
"""把 sentence.txt 的例句同步进 vocab/encyclopedia.html。

- 以 sentence.txt 为准，逐词覆盖 <h3 class="entry-word">W</h3><p class="entry-sentence">S</p> 里的 S
- 不新增/删除词条（页面的词表结构保持原样）
- sentence.txt 里找不到的词，保持原样并记入日志
- 内容无变化时不写文件（避免无谓的 diff）

写入时会把 & < > 转义成 HTML 实体；比较时两边都做反转义，
所以「已是正确转义」的句子不会被反复改写。

用法:
    python3 tools/sync_sentences.py            # 同步（有变化才写）
    python3 tools/sync_sentences.py --check    # 只检查，不写；有差异则 exit 1
"""
import html as H
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENTENCE = os.path.join(BASE, "sentence.txt")
ENCYCLOPEDIA = os.path.join(BASE, "vocab", "encyclopedia.html")

ENTRY_RE = re.compile(
    r'<h3 class="entry-word">(.*?)</h3><p class="entry-sentence">(.*?)</p>', re.S
)


def norm(s):
    """反转义 + 压缩空白，得到用于比较的纯净文本。"""
    return re.sub(r"\s+", " ", H.unescape(s)).strip()


def esc(s):
    """转义成可安全放进 HTML 文本节点的形式。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_sentences():
    data = {}
    with open(SENTENCE, encoding="utf-8") as fh:
        for line in fh:
            if ":" not in line:
                continue
            word, sentence = line.split(":", 1)
            key = word.strip().lower()
            if not key:
                continue
            data[key] = re.sub(r"\s+", " ", sentence).strip()
    return data


def main():
    check_only = "--check" in sys.argv[1:]

    if not os.path.isfile(SENTENCE):
        print(f"[sync-sentences] 缺少 {SENTENCE}，跳过", file=sys.stderr)
        return 0
    if not os.path.isfile(ENCYCLOPEDIA):
        print(f"[sync-sentences] 缺少 {ENCYCLOPEDIA}，跳过", file=sys.stderr)
        return 0

    sentences = load_sentences()
    with open(ENCYCLOPEDIA, encoding="utf-8") as fh:
        src = fh.read()

    stats = {"updated": 0, "same": 0, "missing": []}

    def repl(m):
        word_raw, sentence_raw = m.group(1), m.group(2)
        key = norm(word_raw).lower()
        if key not in sentences:
            stats["missing"].append(key)
            return m.group(0)
        plain = sentences[key]
        if plain == norm(sentence_raw):
            # 内容已一致 -> 原样保留，避免无谓 diff
            stats["same"] += 1
            return m.group(0)
        new = esc(plain)
        stats["updated"] += 1
        return (
            f'<h3 class="entry-word">{word_raw}</h3>'
            f'<p class="entry-sentence">{new}</p>'
        )

    out = ENTRY_RE.sub(repl, src)

    total = stats["updated"] + stats["same"] + len(stats["missing"])
    if stats["missing"]:
        print(
            f"[sync-sentences] sentence.txt 中缺失 {len(stats['missing'])} 个词条"
            f"（保持原样）: {', '.join(stats['missing'][:10])}",
            file=sys.stderr,
        )

    if stats["updated"] == 0:
        print(f"[sync-sentences] 例句已是最新，无需改动（{total} 词条）")
        return 0

    if check_only:
        print(
            f"[sync-sentences] 检测到 {stats['updated']}/{total} 条例句与 sentence.txt 不一致",
            file=sys.stderr,
        )
        return 1

    with open(ENCYCLOPEDIA, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(
        f"[sync-sentences] 已同步 {stats['updated']}/{total} 条例句 -> {ENCYCLOPEDIA}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
