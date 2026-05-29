#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse study.txt into structured vocabulary records."""

from __future__ import annotations

import json
import re
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[2]
STUDY = SCRIPTS_ROOT / "study.txt"
OUT = Path(__file__).resolve().parents[1] / "data" / "vocab.json"

ENTRY_RE = re.compile(
    r"^(\d+),\s*(.+?)\s+英译中\s*$",
    re.MULTILINE,
)
PHONETIC_RE = re.compile(r"\[([^\]]+)\]")


def parse_study(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    entries: list[dict] = []
    blocks = re.split(r"\n未分组单词\n", text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        if not lines:
            continue
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
        word = rest.strip()
        gloss_lines = []
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("【"):
                continue
            if line:
                gloss_lines.append(line)
        entries.append(
            {
                "id": num,
                "word": word,
                "phonetic": phonetic,
                "gloss_zh": "\n".join(gloss_lines),
            }
        )
    entries.sort(key=lambda e: e["id"])
    return entries


def slice_unit(entries: list[dict], start_id: int, size: int = 25) -> list[dict]:
    return [e for e in entries if start_id <= e["id"] < start_id + size]


def main() -> None:
    if not STUDY.exists():
        raise SystemExit(f"study.txt not found: {STUDY}")
    entries = parse_study(STUDY)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Parsed {len(entries)} entries -> {OUT}")


if __name__ == "__main__":
    main()
