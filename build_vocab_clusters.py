#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot builder: parse study.txt, cluster, write vocab-stories/data and index."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STUDY = ROOT / "study.txt"
OUT_DATA = ROOT / "vocab-stories" / "data"
OUT_UNITS = ROOT / "vocab-stories" / "units"
INDEX = ROOT / "vocab-stories" / "index.md"

UNIT_SIZE = 25
MORPH_EVERY = 5

ENTRY_RE = re.compile(r"^(\d+),\s*(.+?)\s+英译中\s*$", re.MULTILINE)
PHONETIC_RE = re.compile(r"\[([^\]]+)\]")

THEME_RULES: list[tuple[str, str, list[str]]] = [
    ("emotion_negative", "情绪·负面", ["怒", "愤", "恨", "恼", "怨", "沮", "丧", "悲", "哀", "闷", "烦", "忌", "委屈", "愤慨", "憎恨", "气愤", "resent"]),
    ("emotion_positive", "情绪·正面", ["喜", "乐", "愉", "快", "兴", "慰", "满足", "欣喜", "愉快", "高兴"]),
    ("emotion_anxiety", "情绪·紧张", ["恐", "惧", "慌", "焦虑", "紧张", "忧", "担心", "不安", "惊慌"]),
    ("attitude_character", "态度·性格", ["傲慢", "谦", "诚", "懒", "笨", "狡猾", "勇敢", "胆小", "专横", "放肆", "冒昧", "粗鲁", "无礼", "高尚", "庸俗", "粗俗"]),
    ("conflict_violence", "冲突·攻击", ["攻", "袭击", "殴打", "暴", "杀", "战", "侵", "冲击", "打斗", "暴力"]),
    ("business_finance", "商业·财务", ["商", "利润", "亏", "赔", "赚", "债", "税", "票", "市", "贸", "联盟", "赤字", "繁荣", "配方", "方案"]),
    ("body_health", "身体·健康", ["体", "身", "病", "伤", "痛", "血", "皮", "骨", "肌", "汗", "脱皮", "剥"]),
    ("nature_plants", "自然·植物", ["树", "林", "花", "草", "叶", "木", "植", "森", "榆", "桦"]),
    ("food_cooking", "饮食·烹饪", ["食", "吃", "烹", "厨", "肉", "面", "饮", "糕", "屑", "屠"]),
    ("movement_action", "动作·移动", ["走", "跑", "跳", "移", "飞", "赶", "奔", "匆忙", "挥", "操"]),
    ("speech_language", "言语·沟通", ["说", "讲", "谈", "诉", "喊", "叫", "语", "嘟", "咕"]),
    ("building_place", "建筑·场所", ["房", "屋", "楼", "建", "桥", "街", "院", "修道", "舱", "隔", "分隔", "烟囱"]),
    ("religion_spiritual", "宗教·精神", ["神", "宗教", "灵", "僧", "修道", "祈祷", "精神", "心灵", "圣歌"]),
    ("death_funeral", "死亡·丧葬", ["死", "葬", "丧", "火化", "火葬"]),
    ("law_order", "法律·秩序", ["法", "罪", "犯", "监", "警", "律"]),
    ("mind_cognition", "思维·认知", ["思", "想", "智", "悟", "疑", "信", "预期", "预料", "期盼", "结论", "确定"]),
    ("sensory_perception", "感官·感知", ["看", "听", "闻", "尝", "触", "响", "轰", "沉闷"]),
    ("social_relation", "社会·关系", ["盟", "友", "敌", "婚", "亲", "伙", "伴", "出席", "存在", "风度", "气质"]),
    ("appearance_quality", "外观·品质", ["美", "丑", "亮", "暗"]),
    ("time_change", "时间·变化", ["久", "暂", "瞬", "始", "终", "变", "改"]),
]

THEME_ORDER = [t[0] for t in THEME_RULES] + ["misc"]

PREFIXES = sorted(
    ["inter", "trans", "super", "under", "over", "anti", "non", "dis", "pre", "mis", "out", "re", "un", "de", "en", "em", "in", "im", "ex", "sub"],
    key=len,
    reverse=True,
)
SUFFIXES = sorted(
    ["tion", "sion", "ment", "ness", "ity", "ous", "ful", "less", "able", "ible", "ive", "ize", "ise", "ism", "ist", "al", "ic", "ly"],
    key=len,
    reverse=True,
)

POS_RE = re.compile(r"^(adj|n|v|adv|vt|vi)\.", re.I)


def parse_study(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    entries: list[dict] = []
    for block in re.split(r"\n未分组单词\n", text):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        m = ENTRY_RE.match(lines[0] + "\n")
        if not m:
            continue
        num = int(m.group(1))
        rest = m.group(2).strip()
        phonetic = None
        pm = PHONETIC_RE.search(rest)
        if pm:
            phonetic = pm.group(1)
            rest = PHONETIC_RE.sub("", rest).strip()
        gloss_lines = [ln.strip() for ln in lines[1:] if ln.strip() and not ln.strip().startswith("【")]
        entries.append(
            {"id": num, "word": rest.strip(), "phonetic": phonetic, "gloss_zh": "\n".join(gloss_lines)}
        )
    entries.sort(key=lambda e: e["id"])
    return entries


def head_word(word: str) -> str:
    w = word.strip().lower()
    return w.split()[0] if " " in w else w


def detect_pos(gloss: str) -> str:
    m = POS_RE.match(gloss.strip())
    return m.group(1).lower() if m else "other"


def morph_family(word: str) -> str | None:
    w = head_word(word)
    for p in PREFIXES:
        if w.startswith(p) and len(w) > len(p) + 2:
            return f"prefix:{p}"
    for s in SUFFIXES:
        if w.endswith(s) and len(w) > len(s) + 2:
            return f"suffix:{s}"
    return None


def assign_theme(entry: dict) -> str:
    gloss = entry.get("gloss_zh", "")
    best_id, best_score = "misc", 0
    for theme_id, _label, keys in THEME_RULES:
        score = sum(1 for k in keys if k in gloss)
        if score > best_score:
            best_score, best_id = score, theme_id
    return best_id


def chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def interleave_units(theme_units: list[dict], morph_units: list[dict]) -> list[dict]:
    result, ti, mi, since = [], 0, 0, 0
    while ti < len(theme_units) or mi < len(morph_units):
        if since >= MORPH_EVERY - 1 and mi < len(morph_units):
            result.append(morph_units[mi])
            mi += 1
            since = 0
        elif ti < len(theme_units):
            result.append(theme_units[ti])
            ti += 1
            since += 1
        elif mi < len(morph_units):
            result.append(morph_units[mi])
            mi += 1
        else:
            break
    return result


def main() -> None:
    entries = parse_study(STUDY)
    by_theme: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_theme[assign_theme(e)].append({**e, "theme": assign_theme(e), "pos": detect_pos(e.get("gloss_zh", ""))})

    def sort_key(e: dict) -> tuple:
        return ({"adj": 0, "v": 1, "n": 2, "adv": 3}.get(e["pos"], 4), e["id"])

    theme_clusters: list[dict] = []
    labels = {tid: lbl for tid, lbl, _ in THEME_RULES}
    labels["misc"] = "杂项·场景收纳"
    for theme_id in THEME_ORDER:
        words = sorted(by_theme.get(theme_id, []), key=sort_key)
        if not words:
            continue
        for i, part in enumerate(chunk(words, UNIT_SIZE)):
            theme_clusters.append(
                {
                    "cluster_id": f"{theme_id}_{i+1}",
                    "type": "theme",
                    "label": labels.get(theme_id, theme_id),
                    "theme_id": theme_id,
                    "words": part,
                    "word_ids": [w["id"] for w in part],
                }
            )

    morph_batch: list[dict] = []
    morph_clusters: list[dict] = []
    morph_pool: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        fam = morph_family(e["word"])
        if fam:
            morph_pool[fam].append(e)
    for _fam, words in sorted(morph_pool.items(), key=lambda kv: -len(kv[1])):
        morph_batch.extend(sorted(words, key=lambda e: e["id"]))
        while len(morph_batch) >= UNIT_SIZE:
            batch = morph_batch[:UNIT_SIZE]
            morph_batch = morph_batch[UNIT_SIZE:]
            morph_clusters.append(
                {
                    "cluster_id": f"morph_{batch[0]['id']}",
                    "type": "morph",
                    "label": f"词形家族·{morph_family(batch[0]['word'])}",
                    "theme_id": "morphology",
                    "words": batch,
                    "word_ids": [w["id"] for w in batch],
                }
            )
    if morph_batch:
        morph_clusters.append(
            {
                "cluster_id": f"morph_tail",
                "type": "morph",
                "label": "词形家族·收尾",
                "theme_id": "morphology",
                "words": morph_batch,
                "word_ids": [w["id"] for w in morph_batch],
            }
        )

    all_units = interleave_units(theme_clusters, morph_clusters)
    for n, u in enumerate(all_units, 1):
        u["unit"] = n

    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_UNITS.mkdir(parents=True, exist_ok=True)
    (OUT_DATA / "vocab.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    clusters_out = [{k: v for k, v in u.items() if k != "words"} for u in all_units]
    (OUT_DATA / "clusters.json").write_text(json.dumps(clusters_out, ensure_ascii=False, indent=2), encoding="utf-8")
    units_words = {
        str(u["unit"]): [
            {
                "id": w["id"],
                "word": w["word"],
                "phonetic": w.get("phonetic"),
                "gloss_zh": w.get("gloss_zh"),
                "sense_in_unit": (w.get("gloss_zh") or "").split("；")[0].split(";")[0][:100],
            }
            for w in u["words"]
        ]
        for u in all_units
    }
    (OUT_DATA / "units.json").write_text(json.dumps(units_words, ensure_ascii=False, indent=2), encoding="utf-8")
    id_to_unit = {wid: u["unit"] for u in all_units for wid in u["word_ids"]}
    (OUT_DATA / "word_to_unit.json").write_text(json.dumps(id_to_unit, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 词库学习单元索引",
        "",
        f"- 词条总数：**{len(entries)}**",
        f"- 单元总数：**{len(all_units)}**（每单元 **{UNIT_SIZE}** 词）",
        f"- 编排：主题簇优先；每 **{MORPH_EVERY}** 单元插入 1 个词形专题",
        "",
        "## 单元列表",
        "",
        "| 单元 | 类型 | 主题 | 词数 | 词号范围 |",
        "|------|------|------|------|----------|",
    ]
    for u in all_units:
        ids = u["word_ids"]
        id_range = f"{min(ids)}–{max(ids)}" if ids else "—"
        lines.append(
            f"| unit-{u['unit']:03d} | {u['type']} | {u['label']} | {len(ids)} | {id_range} |"
        )
    INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")

    u1 = all_units[0]
    print(f"OK entries={len(entries)} units={len(all_units)}")
    print("unit-001:", ", ".join(w["word"] for w in u1["words"]))
    # export unit 1 word list for story authoring
    (OUT_DATA / "unit-001-words.json").write_text(
        json.dumps(units_words["1"], ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
