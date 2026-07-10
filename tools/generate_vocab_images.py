#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 study.txt 为词汇 AI 生成配图（Pollinations 免费接口），保存到 images/。
按「英文单词 + 中文释义」构造提示词，底部叠加小写英文与中文。
本机执行：tools\\run_generate_vocab_images.cmd（会 cd 到 ReleasePlanCheck 再运行）
"""

from __future__ import annotations

import argparse
import io
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_ROOT = Path(__file__).resolve().parent.parent

CARD_W, CARD_H = 400, 560
IMAGE_H = 340
TEXT_TOP = IMAGE_H + 8
USER_AGENT = "VocabImageBot/1.0 (local study script)"
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

ENTRY_RE = re.compile(r"^\d+,\s*([a-zA-Z][a-zA-Z-]*?)\s*(?:\[.*?\])?\s+英译中")
POS_RE = re.compile(r"^[a-z]+\.\s*", re.I)


def parse_entries(study_file: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    lines = study_file.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        m = ENTRY_RE.match(lines[i].strip())
        if m:
            word = m.group(1).strip().lower()
            meaning = ""
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if nxt and not nxt.startswith("未分组") and not ENTRY_RE.match(nxt):
                    meaning = POS_RE.sub("", nxt).strip()
                    meaning = re.split(r"[；;]", meaning, maxsplit=1)[0].strip()
            entries.append((word, meaning))
        i += 1
    return entries


def _primary_cn_gloss(meaning: str) -> str:
    """取释义行第一个中文义项（去掉词性前缀与分号后内容）。"""
    if not meaning:
        return ""
    gloss = POS_RE.sub("", meaning).strip()
    gloss = re.split(r"[；;]", gloss, maxsplit=1)[0].strip()
    parts = re.split(r"[，,（(]", gloss)
    return parts[0].strip()


# 中文义项关键词 -> 直白英文画面（优先于泛化模板）
VISUAL_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("烟囱",), "a brick house with a tall chimney on the roof, gray smoke rising from the chimney"),
    (("屠夫",), "a butcher shop: fresh red meat on a wooden block, a large metal cleaver"),
    (("肉店",), "a butcher shop counter with hanging meat and a meat cleaver"),
    (
        ("亏损", "赤字", "不足额"),
        "an empty wallet opened with no money inside, a few coins falling out, "
        "red downward arrow showing financial loss",
    ),
    (("缺乏", "不足"), "an almost-empty container with only a tiny amount left at the bottom"),
]


def _lookup_visual_hint(cn: str, meaning: str) -> str:
    text = f"{cn} {meaning}"
    for keywords, scene in VISUAL_HINTS:
        if any(kw in text for kw in keywords):
            return scene
    return ""


def build_prompt(word: str, meaning: str) -> str:
    cn = _primary_cn_gloss(meaning)
    hint = _lookup_visual_hint(cn, meaning)

    if hint:
        scene = f"Show exactly: {hint}. This illustrates the word '{word}'"
        if cn:
            scene += f" (Chinese meaning: {cn})"
        scene += "."
    elif cn:
        scene = (
            f"Show ONE clear real-world object or simple everyday scene for "
            f"the Chinese word '{cn}' (English: {word}). "
            f"Choose the most literal, common visual that a child instantly recognizes."
        )
    else:
        scene = (
            f"Show ONE clear real-world object or simple everyday scene for "
            f"the English word '{word}'. "
            f"Choose the most literal, common visual example."
        )

    return (
        f"{scene} "
        "Children's textbook illustration, flat cartoon, simple shapes, "
        "bright friendly colors, plain white background, centered single subject, "
        "large clear silhouette, easy for language learners to understand at a glance."
    )


def build_negative_prompt() -> str:
    return (
        "abstract art, surreal, symbolic only, metaphorical, dreamlike, artistic, "
        "map, globe, world map, chart, graph, diagram, infographic, "
        "random people, crowd, group photo, portrait, face close-up, "
        "text, letters, words, numbers, labels, caption, watermark, logo, "
        "dark background, busy cluttered background, blurry, "
        "photorealistic, 3d render, oil painting, watercolor, sketch, messy, horror"
    )


def fetch_ai_image(word: str, meaning: str, *, verbose: bool = False) -> Image.Image | None:
    prompt = build_prompt(word, meaning)
    negative = build_negative_prompt()
    if verbose:
        print(f"    prompt: {prompt[:120]}...")
    encoded = urllib.parse.quote(prompt)
    encoded_neg = urllib.parse.quote(negative)
    seed = abs(hash(word)) % 100000
    url = (
        f"{POLLINATIONS_BASE}/{encoded}"
        f"?width=400&height=340&seed={seed}&nologo=true&model=flux"
        f"&negative={encoded_neg}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data))
        img.load()
        if img.width < 80 or img.height < 80:
            return None
        return img
    except (urllib.error.URLError, OSError, Image.UnidentifiedImageError):
        return None


def load_font(size: int, chinese: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if chinese:
        candidates = (
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/simsun.ttc"),
        )
    else:
        candidates = (
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        )
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def wrap_by_pixels(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = ch
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len("".join(lines)) < len(text):
        last = lines[-1]
        while draw.textlength(last + "…", font=font) > max_width and last:
            last = last[:-1]
        lines[-1] = (last + "…") if last else "…"
    return lines


def draw_fallback_panel(draw: ImageDraw.ImageDraw, word: str, meaning: str) -> None:
    draw.rectangle([16, 16, CARD_W - 16, IMAGE_H - 16], fill="#eef2f7", outline="#c5d0de", width=2)
    en_font = load_font(42, chinese=False)
    cn_font = load_font(28, chinese=True)
    draw.text((CARD_W // 2, IMAGE_H // 2 - 24), word, fill="#1a1a1a", anchor="mm", font=en_font)
    if meaning:
        for i, line in enumerate(wrap_by_pixels(draw, meaning, cn_font, CARD_W - 48, 3)):
            draw.text(
                (CARD_W // 2, IMAGE_H // 2 + 20 + i * 32),
                line,
                fill="#3d5a80",
                anchor="mm",
                font=cn_font,
            )


def make_card(word: str, meaning: str, photo: Image.Image | None) -> Image.Image:
    card = Image.new("RGB", (CARD_W, CARD_H), "white")
    draw = ImageDraw.Draw(card)

    if photo is not None:
        photo = photo.convert("RGB")
        max_w, max_h = CARD_W - 32, IMAGE_H - 32
        photo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        x = (CARD_W - photo.width) // 2
        y = (IMAGE_H - photo.height) // 2
        card.paste(photo, (x, y))
    else:
        draw_fallback_panel(draw, word, meaning)

    en_font = load_font(30, chinese=False)
    cn_font = load_font(22, chinese=True)
    draw.text((CARD_W // 2, TEXT_TOP + 18), word, fill="#111111", anchor="mm", font=en_font)
    if meaning:
        y = TEXT_TOP + 52
        for line in wrap_by_pixels(draw, meaning, cn_font, CARD_W - 32, 2):
            draw.text((CARD_W // 2, y), line, fill="#555555", anchor="mm", font=cn_font)
            y += 28
    return card


def output_path(word: str, root: Path) -> Path:
    safe = re.sub(r'[<>:"/\\|?*]', "_", word)
    return root / "images" / f"{safe}.png"


def generate_one(word: str, meaning: str, root: Path, force: bool = False) -> bool:
    dest = output_path(word, root)
    if dest.exists() and not force:
        print(f"  skip  {word} (exists)")
        return True

    photo = fetch_ai_image(word, meaning, verbose=force)
    card = make_card(word, meaning, photo)
    (root / "images").mkdir(parents=True, exist_ok=True)
    card.save(dest, format="PNG")
    tag = "ai" if photo else "text"
    print(f"  {tag}  {word} | {meaning[:24]}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 为 study.txt 词汇生成配图")
    parser.add_argument("--word", help="只生成指定单词")
    parser.add_argument("--limit", type=int, help="最多处理 N 个词")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="覆盖已有图片")
    parser.add_argument("--delay", type=float, default=2.0, help="每张图间隔秒数")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()

    root = args.root.resolve()
    study_file = root / "study.txt"
    if not study_file.exists():
        raise SystemExit(f"找不到 {study_file}")

    entries = parse_entries(study_file)
    if args.word:
        target = args.word.strip().lower()
        entries = [(w, m) for w, m in entries if w == target]
        if not entries:
            raise SystemExit(f"找不到单词: {target}")
    else:
        entries = entries[args.offset :]
        if args.limit:
            entries = entries[: args.limit]

    print(f"共 {len(entries)} 个词，AI 生图 -> {root / 'images'}")
    for i, (word, meaning) in enumerate(entries):
        generate_one(word, meaning, root, force=args.force)
        if i < len(entries) - 1:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
