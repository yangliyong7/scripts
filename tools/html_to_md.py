#!/usr/bin/env python3
"""Convert season/NNNN.html to docs markdown transcript.

Usage:
    py tools/html_to_md.py 0507
    py tools/html_to_md.py 508
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMON_CHARACTERS = {
    "Phoebe", "Rachel", "Ross", "Chandler", "Monica", "Joey", "All",
    "Gunther", "Estelle", "Janice", "Richard", "Mike", "David",
    "Mrs. Bing", "Mr. Bing", "Mr. Geller", "Mrs. Geller",
    "The Teacher", "The Doctor", "The Paramedic", "The Man",
}

DEFAULT_SECTION_MARKERS = {
    "Opening Credits", "Commercial Break", "Ending Credits", "End",
    "Present Day",
}


def decode_entities(s: str) -> str:
    return (
        s.replace("&#151;", "\u2014")
        .replace("&#133;", "\u2026")
        .replace("&#146;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )


def strip_tags(s: str) -> str:
    s = re.sub(r"</?b>", "", s)
    s = re.sub(r"</?strong>", "", s, flags=re.I)
    s = re.sub(r"</?i>", "", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return decode_entities(s).strip()


def episode_code(arg: str) -> tuple[str, str]:
    digits = re.sub(r"\D", "", arg)
    if len(digits) < 4:
        raise SystemExit(f"Invalid episode: {arg!r} (need 4 digits, e.g. 0507)")
    season, ep = digits[:2], digits[2:4]
    return f"{season}{ep}", f"S{season}E{ep}"


def title_slug(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")
    return slug


def extra_section_markers(html: str) -> set[str]:
    markers = set()
    for m in re.finditer(
        r'<p\s+align="center"[^>]*>\s*<strong>(.*?)</strong>',
        html,
        re.I | re.S,
    ):
        text = strip_tags(m.group(1))
        if text and text not in DEFAULT_SECTION_MARKERS:
            markers.add(text)
    return markers


def convert(ep_arg: str) -> Path:
    file_code, display_code = episode_code(ep_arg)
    html_path = ROOT / "season" / f"{file_code}.html"
    if not html_path.exists():
        raise SystemExit(f"Not found: {html_path}")

    html = html_path.read_text(encoding="windows-1252", errors="replace")
    section_markers = DEFAULT_SECTION_MARKERS | extra_section_markers(html)

    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    title = strip_tags(title_match.group(1)) if title_match else "Unknown"

    written = re.search(r"Written [Bb]y:\s*(.*?)(?:<br|</p>)", html, re.I | re.S)
    written_by = strip_tags(written.group(1)) if written else ""

    trans = re.search(r"Transcribed by:.*?>(.*?)</a>", html, re.I | re.S)
    trans_by = strip_tags(trans.group(1)) if trans else "Eric Aasen"

    help_from = re.search(r"With Help From:.*?>(.*?)</a>", html, re.I | re.S)
    help_by = strip_tags(help_from.group(1)) if help_from else ""

    paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.I | re.S)

    lines: list[str] = [
        f"# Friends {display_code} - {title}",
        "",
        f"**Written by:** {written_by}",
        f"**Transcribed by:** {trans_by}",
    ]
    if help_by:
        lines.append(f"**With help from:** {help_by}")
    lines.extend(["", "---", ""])

    scene_num = 0
    for raw in paras:
        text = strip_tags(raw)
        if not text or text.startswith("contrl08") or "FrontPageMap" in text:
            continue
        if re.match(r"^(Written [Bb]y|Transcribed by|With Help From):", text, re.I):
            continue

        if text.startswith("[Scene:"):
            scene_num += 1
            loc = text[7:-1].strip() if text.endswith("]") else text[7:].strip()
            lines.extend([f"## Scene {scene_num}: {loc}", ""])
            continue

        if text in section_markers:
            lines.extend(["---", "", f"## {text}", ""])
            continue

        if text.startswith("[Cut to"):
            lines.extend([f"*{text}*", ""])
            continue

        m = re.match(r"^([^:]+):\s*(.*)$", text, re.S)
        if m:
            name = re.sub(r"\s+", " ", m.group(1).strip())
            dialogue = m.group(2).strip()
            if name in COMMON_CHARACTERS or (
                len(name) < 40
                and name
                and name[0].isupper()
                and "http" not in name
                and not name.startswith("Note")
            ):
                lines.extend([f"**{name}:** {dialogue}", ""])
                continue

        if text.startswith("(") or (
            text.startswith("[") and not text.startswith("[Scene:")
        ):
            lines.extend([f"*{text}*", ""])
            continue

        lines.extend([f"*{text}*", ""])

    lines.extend(["---", "", "**END**"])
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))

    out_path = (
        ROOT / "docs" / f"Friends_{display_code}_{title_slug(title)}.md"
    )
    out_path.write_text(out, encoding="utf-8")
    print(f"Done: {out_path.name} — {scene_num} scenes, {len(out)} chars")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: py tools/html_to_md.py <episode>")
    convert(sys.argv[1])
