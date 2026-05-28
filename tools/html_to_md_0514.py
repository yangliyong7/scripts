import re
from pathlib import Path

html = Path(r"c:\Users\ICN00069\Downloads\scripts\season\0514.html").read_text(
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
    "Gunther",
    "Dr. Ledbetter",
    "Phoebe and Rachel",
    "Chandler and Monica",
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
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return decode_entities(s).strip()


title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
title = strip_tags(title_match.group(1)) if title_match else "The One Where Everyone Finds Out"

written = re.search(r"Written by:\s*(.*?)(?:<br|</p>)", html, re.I | re.S)
written_by = strip_tags(written.group(1)) if written else "Alexa Junge"

trans = re.search(r"Transcribed by:.*?>(.*?)</a>", html, re.I | re.S)
trans_by = strip_tags(trans.group(1)) if trans else "Eric Aasen"

paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.I | re.S)

lines: list[str] = [
    f"# Friends S05E14 - {title}",
    "",
    f"**Written by:** {written_by}",
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
        if name in CHARACTERS or (len(name) < 25 and name[0].isupper()):
            lines.extend([f"**{name}:** {dialogue}", ""])
            continue

    if text.startswith("(") or (text.startswith("[") and not text.startswith("[Scene:")):
        lines.extend([f"*{text}*", ""])
        continue

    lines.extend([f"*{text}*", ""])

lines.extend(["---", "", "**END**"])

out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))

notes = """

---

## 笔记

### 本集梗概

Phoebe 和 Rachel 在 Ugly Naked Guy 公寓窗外 **撞见 Monica 和 Chandler 亲热**，秘密恋情曝光（对她们而言）。Joey 早就知道。众人决定 **暂不摊牌**，互相整蛊，最终 Chandler 在 Phoebe 的「诱惑」下 **喊出 I love Monica**，秘密才真正公开——但 Ross 仍不知情（本集结尾 Ross 搬新公寓，又透过窗户看见 Monica 和 Chandler……）。

### 关键台词与表达

| 台词 / 表达 | 含义 |
|-------------|------|
| **doing it** | 双关：表面「洗衣服/买菜」，实际指 **上床**。Rachel 的 *Phone doing it* 是叠梗。 |
| **sad Linda from camp** | Monica 曾用来当幌子的借口（跟夏令营认识的 Linda 煲电话粥），Phoebe 后知后觉这也是掩护。 |
| **I can't take any more secrets!** | Joey 受不了保密压力：Rachel 的秘密、Monica/Chandler 的秘密、还有自己的（Hugsy 企鹅）。 |
| **Hugsy, my bedtime penguin pal** | Joey 抱睡用的企鹅玩偶，被 Rachel 吐槽「你哪有什么秘密」。 |
| **the strongest tool at my disposal. My sexuality.** | Phoebe 计划用 **魅力/调情** 整 Chandler，让 Monica 吃醋。 |
| **watch, learn, and don't eat my cookie** | 「看着学，别吃我的曲奇」——要去撩 Chandler 了。 |
| **Hello Mr. Bicep!** | 摸胳膊时的夸张调情。 |
| **charming in a sexless kind of way** | Monica 圆场：Phoebe 以前觉得 Chandler **没性感、像无性恋**。 |
| **they know that you know and they don't know that Rachel knows** | 经典「谁知道谁知道」混乱（Who knows what）。 |
| **the messers become the messies** | Chandler 金句：整人的人反被整。 |
| **they don't know that we know they know we know** | 多层「知道链」——两边都在装不知道。 |
| **Ahh yes, the messers become the messies!** | 同上，本集核心 running gag。 |
| **I'm in love with Monica!!** | 整蛊游戏中 Chandler 崩溃告白，全剧名场面。 |
| **Quite a competitor** | Chandler 夸 Phoebe 这场「对决」玩得很狠。 |
| **GET OFF MY SISTER!!!!!!!!!!!!!** | 片尾 Ross 新公寓窗外又见 Monica/Chandler，旧习复发（呼应 E15 开头 Ross 抓包）。 |

### 文化 / 背景

- **Ugly Naked Guy**：对面公寓常裸体的邻居，本集要搬走，Ross 想租他的公寓。
- **mini-muffins bribe**：Ross 用一篮小玛芬「贿赂」房东，结果送的是 **最小那篮**。
- **Naked Ross**：Ross 为套近乎也脱光去 UNG 家，被朋友们从窗口看见，称 *Naked Ross*。
- **本集标题** *The One Where Everyone Finds Out*：众人（几乎）都知道 Chandler/Monica 在一起；Ross 是例外直到后续。

### 场景索引

1. Monica and Rachel's — 中餐馆，UNG 搬家  
2. Ugly Naked Guy's apartment — 发现 M&C 窗口亲热  
3. Central Perk — 秘密、整蛊计划、Phoebe 撩 Chandler  
4. Chandler's bedroom — Monica 否认 Phoebe 会看上 Chandler  
5. Monica and Rachel's — 塞洗衣、Ross 玛芬、Phoebe 捏屁股  
6. Chandler, Joey, and Ross's — Joey/Hugsy，M&C 得知 Phoebe/Rachel 知道  
7. Monica and Rachel's — Ross 望远镜、电话 seduction 反击  
8. Outside UNG's apartment — Naked Ross  
9. Monica and Rachel's — 两派对峙、Naked Ross 窗口  
10. Monica and Rachel's — Phoebe 约会准备  
11. Chandler, Joey, and Ross's — Chandler 约会准备  
12. Hallway / Apartment — Phoebe vs Chandler 对决，告白  
13. Ross's new apartment — 片尾 Ross 再爆发  
"""

Path(
    r"c:\Users\ICN00069\Downloads\scripts\docs\Friends_S05E14_The_One_Where_Everyone_Finds_Out.md"
).write_text(out + notes, encoding="utf-8")
print(f"Done: {scene_num} scenes, {len(out + notes)} chars")
