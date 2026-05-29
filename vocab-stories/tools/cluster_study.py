#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cluster vocabulary by theme, synonym hints, and morphology; build units of 25."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from parse_study import parse_study

SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
STUDY = SCRIPTS_ROOT / "study.txt"
DATA = Path(__file__).resolve().parents[1] / "data"
UNIT_SIZE = 25
MORPH_EVERY = 5  # every 5th unit is morphology-focused

THEME_RULES: list[tuple[str, str, list[str]]] = [
    ("emotion_negative", "情绪·负面", ["怒", "愤", "恨", "恼", "怨", "沮", "丧", "悲", "哀", "闷", "烦", "忌", "委屈", "愤慨", "憎恨", "气愤"]),
    ("emotion_positive", "情绪·正面", ["喜", "乐", "愉", "快", "兴", "慰", "满足", "欣喜", "愉快", "高兴"]),
    ("emotion_anxiety", "情绪·紧张", ["恐", "惧", "慌", "焦虑", "紧张", "忧", "担心", "不安", "惊慌"]),
    ("attitude_character", "态度·性格", ["傲慢", "谦", "诚", "懒", "笨", "狡猾", "勇敢", "胆小", "专横", "放肆", "冒昧", "粗鲁", "无礼", "高尚", "庸俗", "粗俗"]),
    ("conflict_violence", "冲突·攻击", ["攻", "袭击", "殴打", "暴", "杀", "战", "侵", "冲击", "打斗", "暴力"]),
    ("business_finance", "商业·财务", ["商", "利润", "亏", "赔", "赚", "债", "税", "票", "市", "贸", "联盟", "赤字", "繁荣", "配方", "方案"]),
    ("body_health", "身体·健康", ["体", "身", "病", "伤", "痛", "血", "皮", "骨", "肌", "汗", "脱皮", "剥", "呼吸", "医"]),
    ("nature_plants", "自然·植物", ["树", "林", "花", "草", "叶", "木", "植", "森", "榆", "桦", "烟囱", "岩"]),
    ("food_cooking", "饮食·烹饪", ["食", "吃", "烹", "厨", "肉", "面", "饮", "烤", "切", "腥", "腥", "糕点", "屑"]),
    ("movement_action", "动作·移动", ["走", "跑", "跳", "移", "飞", "赶", "奔", "匆忙", "挥", "操", "使用"]),
    ("speech_language", "言语·沟通", ["说", "讲", "谈", "诉", "喊", "叫", "语", "嘟", "咕", "嚷"]),
    ("building_place", "建筑·场所", ["房", "屋", "楼", "建", "桥", "街", "院", "修道", "舱", "隔", "分隔"]),
    ("religion_spiritual", "宗教·精神", ["神", "宗教", "灵", "僧", "修道", "祈祷", "精神", "心灵", "圣歌"]),
    ("death_funeral", "死亡·丧葬", ["死", "葬", "丧", "火化", "火葬", "灵"]),
    ("law_order", "法律·秩序", ["法", "罪", "犯", "监", "警", "院", "律", "合法", "非法"]),
    ("mind_cognition", "思维·认知", ["思", "想", "智", "悟", "疑", "信", "预期", "预料", "期盼", "结论", "确定"]),
    ("sensory_perception", "感官·感知", ["看", "听", "闻", "尝", "触", "闷", "响", "轰", "沉闷", "刺眼"]),
    ("appearance_quality", "外观·品质", ["美", "丑", "亮", "暗", "颜色", "形状", "大小"]),
    ("time_change", "时间·变化", ["久", "暂", "瞬", "始", "终", "变", "改", "增", "减"]),
    ("social_relation", "社会·关系", ["盟", "友", "敌", "婚", "亲", "伙", "伴", "出席", "存在", "风度"]),
]

PREFIXES = [
    "un", "re", "pre", "dis", "mis", "over", "under", "out",
    "anti", "non", "de", "en", "em", "in", "im", "ex", "sub", "super", "inter", "trans",
]
SUFFIXES = [
    "tion", "sion", "ment", "ness", "ity", "ous", "ful", "less",
    "able", "ible", "ive", "ize", "ise", "al", "ic", "ly", "ism", "ist",
]

# Learning order: theme clusters first (pedagogy-friendly), then catch-all
THEME_ORDER = [
    "emotion_negative",
    "emotion_positive",
    "emotion_anxiety",
    "attitude_character",
    "social_relation",
    "mind_cognition",
    "conflict_violence",
    "business_finance",
    "body_health",
    "food_cooking",
    "movement_action",
    "speech_language",
    "sensory_perception",
    "building_place",
    "nature_plants",
    "religion_spiritual",
    "death_funeral",
    "law_order",
    "appearance_quality",
    "time_change",
    "misc",
]

POS_RE = re.compile(r"^(adj|n|v|adv|vt|vi|prep|conj)\.", re.I)


def head_word(word: str) -> str:
    w = word.strip().lower()
    return w.split()[0] if " " in w else w


def detect_pos(gloss: str) -> str:
    m = POS_RE.match(gloss.strip())
    if m:
        return m.group(1).lower()
    if gloss.startswith("adj") or "adj." in gloss[:8]:
        return "adj"
    if gloss.startswith("n") or "n." in gloss[:6]:
        return "n"
    if gloss.startswith("v") or "vt" in gloss[:4] or "vi" in gloss[:4]:
        return "v"
    return "other"


def morph_family(word: str) -> str | None:
    w = head_word(word)
    for p in sorted(PREFIXES, key=len, reverse=True):
        if w.startswith(p) and len(w) > len(p) + 2:
            return f"prefix:{p}"
    for s in sorted(SUFFIXES, key=len, reverse=True):
        if w.endswith(s) and len(w) > len(s) + 2:
            return f"suffix:{s}"
    return None


def score_theme(gloss: str) -> tuple[str, int]:
    best_id = "misc"
    best_score = 0
    for theme_id, _label, keys in THEME_RULES:
        score = sum(1 for k in keys if k in gloss)
        if score > best_score:
            best_score = score
            best_id = theme_id
    return best_id, best_score


def assign_theme(entry: dict) -> str:
    gloss = entry.get("gloss_zh", "")
    theme, score = score_theme(gloss)
    if score == 0:
        w = head_word(entry["word"])
        if any(k in gloss for k in ("人", "者", "员", "家")):
            return "social_relation"
        if len(w) <= 3:
            return "misc"
    return theme


def chunk(items: list[dict], size: int) -> list[list[dict]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_morph_pool(entries: list[dict]) -> dict[str, list[dict]]:
    pools: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        fam = morph_family(e["word"])
        if fam:
            pools[fam].append(e)
    return pools


def interleave_units(theme_units: list[dict], morph_units: list[dict]) -> list[dict]:
    """Place one morphology unit after every MORPH_EVERY-1 theme units."""
    result: list[dict] = []
    ti, mi = 0, 0
    theme_since_morph = 0
    while ti < len(theme_units) or mi < len(morph_units):
        if theme_since_morph >= MORPH_EVERY - 1 and mi < len(morph_units):
            result.append(morph_units[mi])
            mi += 1
            theme_since_morph = 0
        elif ti < len(theme_units):
            result.append(theme_units[ti])
            ti += 1
            theme_since_morph += 1
        elif mi < len(morph_units):
            result.append(morph_units[mi])
            mi += 1
        else:
            break
    return result


def main() -> None:
    entries = parse_study(STUDY)
    DATA.mkdir(parents=True, exist_ok=True)

    by_theme: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        theme = assign_theme(e)
        e2 = {**e, "theme": theme, "pos": detect_pos(e.get("gloss_zh", ""))}
        by_theme[theme].append(e2)

    # Sort within theme: adj first for emotion/attitude, then by id
    def sort_key(e: dict) -> tuple:
        pos_rank = {"adj": 0, "v": 1, "n": 2, "adv": 3}.get(e["pos"], 4)
        return (pos_rank, e["id"])

    theme_clusters: list[dict] = []
    for theme_id in THEME_ORDER:
        words = sorted(by_theme.get(theme_id, []), key=sort_key)
        if not words:
            continue
        label = next((lbl for tid, lbl, _ in THEME_RULES if tid == theme_id), theme_id)
        if theme_id == "misc":
            label = "杂项·场景收纳"
        for i, chunk_words in enumerate(chunk(words, UNIT_SIZE)):
            theme_clusters.append(
                {
                    "cluster_id": f"{theme_id}_{i+1}",
                    "type": "theme",
                    "theme_id": theme_id,
                    "label": label,
                    "part": i + 1,
                    "word_ids": [w["id"] for w in chunk_words],
                    "words": chunk_words,
                }
            )

    # Morphology units: group by prefix family (largest families first)
    morph_pool = build_morph_pool(entries)
    morph_clusters: list[dict] = []
    families = sorted(morph_pool.items(), key=lambda kv: -len(kv[1]))
    morph_batch: list[dict] = []
    for fam, words in families:
        morph_batch.extend(sorted(words, key=lambda e: e["id"]))
        while len(morph_batch) >= UNIT_SIZE:
            batch = morph_batch[:UNIT_SIZE]
            morph_batch = morph_batch[UNIT_SIZE:]
            morph_clusters.append(
                {
                    "cluster_id": f"morph_{batch[0]['id']}",
                    "type": "morph",
                    "theme_id": "morphology",
                    "label": f"词形家族·{morph_family(batch[0]['word']) or 'mixed'}",
                    "part": len(morph_clusters) + 1,
                    "word_ids": [w["id"] for w in batch],
                    "words": batch,
                }
            )
    if morph_batch:
        morph_clusters.append(
            {
                "cluster_id": f"morph_tail_{morph_batch[0]['id']}",
                "type": "morph",
                "theme_id": "morphology",
                "label": "词形家族·收尾",
                "part": len(morph_clusters) + 1,
                "word_ids": [w["id"] for w in morph_batch],
                "words": morph_batch,
            }
        )

    all_units = interleave_units(theme_clusters, morph_clusters)
    for n, u in enumerate(all_units, start=1):
        u["unit"] = n

    # Slim clusters for JSON (no duplicate full word dict if large)
    clusters_out = []
    for u in all_units:
        clusters_out.append(
            {
                "unit": u["unit"],
                "type": u["type"],
                "cluster_id": u["cluster_id"],
                "label": u["label"],
                "theme_id": u["theme_id"],
                "word_ids": u["word_ids"],
            }
        )

    id_to_unit = {wid: u["unit"] for u in all_units for wid in u["word_ids"]}
    units_words = {
        str(u["unit"]): [
            {
                "id": w["id"],
                "word": w["word"],
                "phonetic": w.get("phonetic"),
                "gloss_zh": w.get("gloss_zh"),
                "sense_in_unit": (w.get("gloss_zh") or "").split("；")[0].split(";")[0][:80],
            }
            for w in u["words"]
        ]
        for u in all_units
    }

    (DATA / "vocab.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA / "clusters.json").write_text(
        json.dumps(clusters_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA / "units.json").write_text(
        json.dumps(units_words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA / "word_to_unit.json").write_text(
        json.dumps(id_to_unit, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Markdown index
    lines = [
        "# 词库学习单元索引",
        "",
        f"- 词条总数：**{len(entries)}**",
        f"- 单元总数：**{len(all_units)}**（每单元 **{UNIT_SIZE}** 词）",
        f"- 编排：主题/近义簇为主，每 **{MORPH_EVERY}** 单元插入 1 个词形专题单元",
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
            f"| [unit-{u['unit']:03d}](units/unit-{u['unit']:03d}.md) "
            f"| {u['type']} | {u['label']} | {len(ids)} | {id_range} |"
        )
    index_path = Path(__file__).resolve().parents[1] / "index.md"
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"entries={len(entries)} units={len(all_units)} theme={len(theme_clusters)} morph={len(morph_clusters)}")
    if all_units:
        u1 = all_units[0]
        print("unit-001 words:", ", ".join(w["word"] for w in u1["words"]))


if __name__ == "__main__":
    main()
