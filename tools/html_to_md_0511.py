#!/usr/bin/env python3
"""Convert season/0511.html to docs markdown transcript."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "season" / "0511.html").read_text(
    encoding="windows-1252", errors="replace"
)

CHARACTERS = {
    "Phoebe",
    "Rachel",
    "Ross",
    "Chandler",
    "Monica",
    "Joey",
    "All",
    "Ben",
    "Jay Leno",
    "Woman",
    "Elizabeth",
    "Elizabeth Hornswoggle",
    "Chandler and Joey",
    "Joey and Rachel",
}


def decode_entities(s: str) -> str:
    return (
        s.replace("&#151;", "—")
        .replace("&#133;", "…")
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


title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
title = strip_tags(title_match.group(1)) if title_match else "The One With All The Resolutions"

tele = re.search(r"Teleplay by:\s*(.*?)(?:<br|</p>)", html, re.I | re.S)
story = re.search(r"Story by:\s*(.*?)(?:<br|</p>)", html, re.I | re.S)
teleplay_by = strip_tags(tele.group(1)) if tele else "Suzie Villandry"
story_by = strip_tags(story.group(1)) if story else "Brian Boyle"

trans = re.search(r"Transcribed by:.*?>(.*?)</a>", html, re.I | re.S)
trans_by = strip_tags(trans.group(1)) if trans else "Eric Aasen"

paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.I | re.S)

lines: list[str] = [
    f"# Friends S05E11 - {title}",
    "",
    f"**Teleplay by:** {teleplay_by}",
    f"**Story by:** {story_by}",
    f"**Transcribed by:** {trans_by}",
    "",
    "---",
    "",
]

scene_num = 0
for raw in paras:
    text = strip_tags(raw)
    if not text or text.startswith("contrl08") or "FrontPageMap" in text:
        continue

    if text.startswith("[Scene:"):
        scene_num += 1
        loc = text[7:-1].strip() if text.endswith("]") else text[7:].strip()
        lines.extend([f"## Scene {scene_num}: {loc}", ""])
        continue

    if text in ("Opening Credits", "Commercial Break", "Ending Credits", "End"):
        lines.extend(["---", "", f"## {text}", ""])
        continue

    if text.startswith("[Cut to"):
        lines.extend([f"*{text}*", ""])
        continue

    m = re.match(r"^([^:]+):\s*(.*)$", text, re.S)
    if m:
        name = re.sub(r"\s+", " ", m.group(1).strip())
        dialogue = m.group(2).strip()
        if (
            name in CHARACTERS
            or (len(name) < 40 and name and name[0].isupper() and "http" not in name)
        ):
            lines.extend([f"**{name}:** {dialogue}", ""])
            continue

    if text.startswith("(") or (text.startswith("[") and not text.startswith("[Scene:")):
        lines.extend([f"*{text}*", ""])
        continue

    if text.startswith("3! 2! 1!") or text == "HAPPY NEW YEAR!!":
        lines.extend([f"**All:** {text}", ""])
        continue

    lines.extend([f"*{text}*", ""])

lines.extend(["---", "", "**END**"])

out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))

Path(ROOT / "docs" / "Friends_S05E11_The_One_With_All_The_Resolutions.md").write_text(
    out, encoding="utf-8"
)
print(f"Done: {scene_num} scenes, {len(out)} chars")
