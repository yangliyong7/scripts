#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate natural US English MP3 via Microsoft Edge neural TTS (edge-tts)."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

import edge_tts

WEB = Path(__file__).resolve().parents[1]
STORIES = WEB / "data" / "stories"
AUDIO = WEB / "audio"

# 美式神经语音（自然度远高于浏览器自带 TTS）
DEFAULT_VOICE = "en-US-JennyNeural"  # 女声叙事
# DEFAULT_VOICE = "en-US-GuyNeural"  # 男声可选


def strip_markdown(text: str) -> str:
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", text)


def part_plaintext(part: dict) -> str:
    return "\n\n".join(strip_markdown(p) for p in part.get("paragraphs", []))


async def synth_one(text: str, out: Path, voice: str, rate: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    comm = edge_tts.Communicate(text, voice, rate=rate)
    await comm.save(str(out))
    print(f"  wrote {out.name} ({out.stat().st_size // 1024} KB)")


async def generate_unit(unit: int, voice: str, rate: str) -> None:
    story_path = STORIES / f"unit-{unit:03d}.json"
    if not story_path.exists():
        raise SystemExit(f"Story not found: {story_path}")
    story = json.loads(story_path.read_text(encoding="utf-8"))
    out_dir = AUDIO / f"unit-{unit:03d}"
    meta = {"unit": unit, "voice": voice, "rate": rate, "parts": []}

    print(f"Unit {unit:03d} -> {out_dir}")
    for part in story.get("parts", []):
        pid = part["id"]
        text = part_plaintext(part)
        if not text.strip():
            continue
        mp3 = out_dir / f"part-{pid}.mp3"
        await synth_one(text, mp3, voice, rate)
        meta["parts"].append({"id": pid, "file": f"part-{pid}.mp3"})

    (out_dir / "manifest.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("done.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--unit", type=int, default=1)
    p.add_argument("--voice", default=DEFAULT_VOICE)
    p.add_argument("--rate", default="+0%", help='e.g. "+5%" faster, "-5%" slower')
    args = p.parse_args()
    asyncio.run(generate_unit(args.unit, args.voice, args.rate))


if __name__ == "__main__":
    main()
