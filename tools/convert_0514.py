import re
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "season" / "0514.html"
OUT = Path(__file__).resolve().parent.parent / "docs" / "Friends_S05E14_The_One_Where_Everyone_Finds_Out.md"

html = HTML.read_text(encoding="windows-1252", errors="replace")

CHARACTERS = {
    "Phoebe", "Rachel", "Ross", "Chandler", "Monica", "Joey", "All",
    "Gunther", "Dr. Ledbetter", "Phoebe and Rachel", "Chandler and Monica",
}


def decode_entities(s: str) -> str:
    return (
        s.replace("&#151;", "—")
        .replace("&#133;", "…")
        .replace("&#146;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )


def strip_tags(s: str) -> str:
    s = re.sub(r"</?b>", "", s)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return decode_entities(re.sub(r"\s+", " ", s)).strip()


title = strip_tags(re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S).group(1))
written_by = strip_tags(re.search(r"Written by:\s*(.*?)(?:<br|</p>)", html, re.I | re.S).group(1))
trans_by = strip_tags(re.search(r"Transcribed by:.*?>(.*?)</a>", html, re.I | re.S).group(1))

lines = [
    f"# Friends S05E14 - {title}",
    "",
    f"**Written by:** {written_by}",
    f"**Transcribed by:** {trans_by}",
    "",
    "---",
    "",
]

scene_num = 0
for raw in re.findall(r"<p[^>]*>(.*?)</p>", html, re.I | re.S):
    text = strip_tags(raw)
    if not text or "FrontPageMap" in text or "contrl08" in text:
        continue

    if text.startswith("[Scene:"):
        scene_num += 1
        loc = text[7:-1].strip() if text.endswith("]") else text[7:].strip()
        lines += [f"## Scene {scene_num}: {loc}", ""]
        continue

    if text in ("Opening Credits", "Commercial Break", "Ending Credits", "End"):
        lines += ["---", "", f"## {text}", ""]
        continue

    if text.startswith("[Cut to"):
        lines += [f"*{text}*", ""]
        continue

    m = re.match(r"^([^:]+):\s*(.*)$", text)
    if m:
        name = m.group(1).strip()
        dialogue = m.group(2).strip()
        if name in CHARACTERS or (len(name) < 25 and name[0].isupper() and "http" not in name):
            lines += [f"**{name}:** {dialogue}", ""]
            continue

    if text.startswith("(") or (text.startswith("[") and not text.startswith("[Scene:")):
        lines += [f"*{text}*", ""]
        continue

    lines += [f"*{text}*", ""]

lines += ["---", "", "**END**"]
OUT.write_text(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)), encoding="utf-8")
print(f"Wrote {OUT.name}: {scene_num} scenes")
