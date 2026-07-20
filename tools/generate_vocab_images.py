#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为词汇生成配图（优先 Pollinations Flux 高清），保存到 images/。
支持 --sample：先抽一批具体名词试做质量。
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

CARD_W, CARD_H = 480, 640
IMAGE_H = 400
TEXT_TOP = IMAGE_H + 10
USER_AGENT = "VocabImageBot/2.0 (local sample HQ)"
# 新端点优先，旧端点兜底
POLLINATIONS_URLS = (
    "https://gen.pollinations.ai/image",
    "https://image.pollinations.ai/prompt",
)

ENTRY_RE = re.compile(r"^\d+,\s*([a-zA-Z][a-zA-Z\-']*?)\s*(?:\[.*?\])?\s+英译中")
POS_RE = re.compile(r"^[a-z]+\.\s*", re.I)

# 试做批次：具体、好出图的名词（来自词库）
SAMPLE_CONCRETE = [
    "chimney",
    "butcher",
    "elm",
    "unagi",
    "puffin",
    "mesh",
    "infant",
    "puddle",
    "shutter",
    "dime",
    "corridor",
    "plumage",
    "valve",
    "lamp",
    "baguette",
    "warship",
    "bouquet",
    "porch",
    "nightstand",
    "anchovy",
    "inlet",
    "cockpit",
    "canopy",
    "crumb",
    "compartment",
    "perspiration",
    "saucer",
    "gasket",
    "ampoule",
    "kayaker",
]


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
    if not meaning:
        return ""
    gloss = POS_RE.sub("", meaning).strip()
    gloss = re.split(r"[；;]", gloss, maxsplit=1)[0].strip()
    parts = re.split(r"[，,（(]", gloss)
    return parts[0].strip()


VISUAL_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("烟囱",), "a red-brick house chimney with thin gray smoke rising into blue sky"),
    (("屠夫",), "a butcher standing behind a wooden block with cuts of fresh meat and a cleaver"),
    (("榆树",), "a tall mature elm tree with full green crown in a park"),
    (("鳗鱼",), "a shiny fresh unagi eel on a ceramic plate"),
    (("善知鸟", "海鹦"), "an Atlantic puffin with colorful beak on a rocky cliff"),
    (("网", "网状"), "a fine metal mesh net held in daylight"),
    (("婴儿",), "a sleeping infant baby in a soft blanket"),
    (("水坑", "泥潭"), "a clear rain puddle on asphalt reflecting sky"),
    (("百叶窗", "护窗"), "white wooden window shutters closed on a house wall"),
    (("硬币", "十分"), "a close-up US dime coin on white surface"),
    (("走廊", "过道"), "a bright empty hotel corridor with soft perspective"),
    (("羽毛",), "colorful bird plumage feathers close-up"),
    (("阀", "活门"), "an industrial metal valve on a pipe"),
    (("灯", "光源"), "a warm glowing table lamp on a nightstand"),
    (("面包", "法棍"), "a fresh golden baguette on a wooden board"),
    (("军舰", "战船"), "a gray warship sailing on calm ocean"),
    (("花束",), "a colorful fresh flower bouquet wrapped in paper"),
    (("门廊",), "a wooden front porch with steps and railing"),
    (("床头",), "a wooden nightstand beside a bed with a small lamp"),
    (("凤尾鱼",), "small salted anchovy fish on a plate"),
    (("湖湾", "河湾"), "a quiet coastal inlet with clear water and rocks"),
    (("驾驶舱",), "airplane cockpit with instrument panels and windshield view"),
    (("顶罩", "华盖"), "a fabric bed canopy draped over a four-poster bed"),
    (("屑",), "bread crumbs scattered on a wooden cutting board"),
    (("隔间", "隔层"), "train compartment seats by a window"),
    (("汗",), "forehead skin with clear sweat droplets"),
    (("茶托", "碟"), "a porcelain saucer under a teacup"),
    (("垫圈",), "a rubber gasket ring on white background"),
    (("安瓿",), "a clear glass medicine ampoule"),
    (("皮船",), "a person paddling a kayak on blue water"),
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
        subject = hint
    elif cn:
        subject = (
            f"one clear real-world object that literally shows '{cn}' "
            f"(English word: {word})"
        )
    else:
        subject = f"one clear real-world object for the English word '{word}'"

    return (
        f"High-quality educational flashcard photo: {subject}. "
        "Single subject centered, sharp focus, natural lighting, "
        "clean simple background, realistic detail, no text, no watermark, "
        "no collage, no abstract symbols, vocabulary textbook style."
    )


def build_negative_prompt() -> str:
    return (
        "text, letters, words, watermark, logo, collage, abstract art, "
        "surreal, symbolic icons, chart, diagram, blurry, low quality, "
        "deformed, extra limbs, busy cluttered background, horror"
    )


def fetch_ai_image(word: str, meaning: str, *, verbose: bool = False) -> Image.Image | None:
    prompt = build_prompt(word, meaning)
    negative = build_negative_prompt()
    if verbose:
        print(f"    prompt: {prompt[:140]}...")
    encoded = urllib.parse.quote(prompt)
    encoded_neg = urllib.parse.quote(negative)
    seed = abs(hash(word)) % 100000
    params = (
        f"width=768&height=640&seed={seed}&nologo=true&model=flux"
        f"&enhance=true&negative_prompt={encoded_neg}"
    )
    for base in POLLINATIONS_URLS:
        url = f"{base}/{encoded}?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=150) as resp:
                data = resp.read()
            if len(data) < 2000:
                continue
            img = Image.open(io.BytesIO(data))
            img.load()
            if img.width < 80 or img.height < 80:
                continue
            return img
        except (urllib.error.URLError, OSError, Image.UnidentifiedImageError) as e:
            if verbose:
                print(f"    fail {base}: {e}")
            continue
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
        max_w, max_h = CARD_W - 24, IMAGE_H - 24
        photo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        x = (CARD_W - photo.width) // 2
        y = (IMAGE_H - photo.height) // 2
        card.paste(photo, (x, y))
    else:
        draw_fallback_panel(draw, word, meaning)

    en_font = load_font(32, chinese=False)
    cn_font = load_font(22, chinese=True)
    draw.text((CARD_W // 2, TEXT_TOP + 20), word, fill="#111111", anchor="mm", font=en_font)
    if meaning:
        y = TEXT_TOP + 56
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

    photo = fetch_ai_image(word, meaning, verbose=True)
    card = make_card(word, meaning, photo)
    (root / "images").mkdir(parents=True, exist_ok=True)
    card.save(dest, format="PNG", optimize=True)
    tag = "ai" if photo else "text"
    print(f"  {tag}  {word} | {meaning[:24]}")
    return photo is not None


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 为 study.txt 词汇生成配图")
    parser.add_argument("--word", help="只生成指定单词")
    parser.add_argument("--sample", action="store_true", help="只生成预选具体名词试做批次")
    parser.add_argument("--limit", type=int, help="最多处理 N 个词")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="覆盖已有图片")
    parser.add_argument("--delay", type=float, default=2.5, help="每张图间隔秒数")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()

    root = args.root.resolve()
    study_file = root / "study.txt"
    if not study_file.exists():
        raise SystemExit(f"找不到 {study_file}")

    all_entries = parse_entries(study_file)
    by_word = {w: m for w, m in all_entries}

    if args.word:
        target = args.word.strip().lower()
        if target not in by_word:
            raise SystemExit(f"找不到单词: {target}")
        entries = [(target, by_word[target])]
    elif args.sample:
        entries = []
        for w in SAMPLE_CONCRETE:
            if w in by_word:
                entries.append((w, by_word[w]))
            else:
                print(f"  warn 样本词不在词库: {w}")
        if args.limit:
            entries = entries[: args.limit]
    else:
        entries = all_entries[args.offset :]
        if args.limit:
            entries = entries[: args.limit]

    print(f"共 {len(entries)} 个词，HQ Flux 生图 -> {root / 'images'}")
    ok = 0
    for i, (word, meaning) in enumerate(entries):
        if generate_one(word, meaning, root, force=args.force):
            ok += 1
        if i < len(entries) - 1:
            time.sleep(args.delay)
    print(f"完成: AI成功 {ok}/{len(entries)}")


if __name__ == "__main__":
    main()
