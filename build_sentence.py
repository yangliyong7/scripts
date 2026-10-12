#!/usr/bin/env python3
"""Build sentence.txt: for each vocab word (from images), find the first
Friends episode sentence containing it. Sorted alphabetically, format `word: sentence`.
Unmatched words are written as `word:` (empty).

Matching strategy (first hit in episode order wins):
  1) exact whole-word match (case-insensitive)
  2) if none, common inflection fallback (word + s/es/ed/d/ing/ly/ion/tion/ment/ness),
     matched as whole word.
"""
import os, re, glob, html

BASE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE, "vocab", "images")
HTML_DIR = os.path.join(BASE, "friends", "html")
OUT = os.path.join(BASE, "sentence.txt")

SUFFIXES = ["s", "es", "ed", "d", "ing", "ly", "ion", "tion", "ment", "ness"]

def word_list():
    words = []
    for p in glob.glob(os.path.join(IMG_DIR, "*.webp")):
        w = os.path.basename(p)[:-5]
        if w.lower() == "placeholder":
            continue
        words.append(w)
    return sorted(set(words), key=lambda s: s.lower())

def strip_html(h):
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = html.unescape(h).replace("\u00a0", " ")
    h = re.sub(r"\s+", " ", h)
    return h

def remove_directions(text):
    """Remove stage directions [..] and parentheticals (..) from the whole text
    before sentence splitting, so bracket contents never span sentence breaks."""
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    return text

def clean_sentence(s):
    """Remove any leftover speaker labels / stray brackets so only the spoken sentence remains."""
    s = s.strip()
    # leading speaker labels like "Ross:", "MR, GELLER:", "All:"
    s = re.sub(r"^\s*[A-Za-z][A-Za-z0-9 ,.'\-]{0,30}:\s*", "", s)
    # stray unbalanced brackets left from nested/odd parentheticals
    s = re.sub(r"^[^()\[\]]*[)\]]\s*", "", s)
    s = s.replace("(", "").replace(")", "").replace("[", "").replace("]", "")
    # stray inline speaker label like "Phoebe: "
    s = re.sub(r"\s+[A-Z][A-Za-z]{1,12}\s*:\s*", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")

def main():
    words = word_list()
    # exact forms
    exact = {w.lower(): w for w in words}
    # inflection forms -> original word (only those without exact match, filled later)
    infl = {}   # form_lower -> original word
    for w in words:
        base = w.lower()
        for suf in SUFFIXES:
            f = base + suf
            if f not in exact and f not in infl:
                infl[f] = w

    # phrase words (contain space) -> compiled regex over raw sentence text
    phrases = {}
    for w in words:
        if " " in w.strip() or "(" in w:
            base = re.escape(w.strip()).replace(r"\ ", r"\s+").replace(r"\ ", r"[\s\-]+")
            # allow optional common suffix (plural/tense) after the phrase
            phrases[w] = re.compile(r"(?<![A-Za-z])" + base + r"(?:s|es|ed|d|ing)?(?![A-Za-z])", re.IGNORECASE)

    found = {}   # original word -> cleaned sentence
    found_raw = {}  # original word -> raw sentence (for matching only)
    files = sorted(glob.glob(os.path.join(HTML_DIR, "*.html")))
    total_sents = 0
    for f in files:
        if len(found) == len(words):
            break
        raw = open(f, encoding="utf-8", errors="ignore").read()
        text = remove_directions(strip_html(raw))
        for s_raw in split_sentences(text):
            if len(s_raw) < 4 or len(s_raw) > 400:
                continue
            s = clean_sentence(s_raw)
            if not s or len(s) < 3:
                continue
            total_sents += 1
            toks = set(t.lower() for t in TOKEN_RE.findall(s))
            # exact hits first
            for t in toks:
                if t in exact:
                    orig = exact[t]
                    if orig not in found:
                        found[orig] = s
            # multi-word phrases
            for orig, rx in phrases.items():
                if orig not in found and rx.search(s):
                    found[orig] = s
            # inflection fallback
            for t in toks:
                if t in infl:
                    orig = infl[t]
                    if orig not in found:
                        found[orig] = s
    lines = [f"{w}: {found.get(w, '')}" for w in words]
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    matched = sum(1 for w in words if w in found)
    print(f"sentences_scanned={total_sents} words={len(words)} matched={matched} unmatched={len(words)-matched}")
    un = [w for w in words if w not in found]
    print("unmatched sample:", un[:40])

if __name__ == "__main__":
    main()
