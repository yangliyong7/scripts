#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 pre-sentence.txt 同步 encyclopedia.html 的词条名与例句。
- 词条名以 pre-sentence.txt 为准（词条重命名：altitudes->altitude 等）
- 例句以 pre-sentence.txt 为准
- pre-sentence 中新增且有配图的词，按分类插入对应分类并按字母序排序
"""
import re, html, os, sys, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENC = os.path.join(ROOT, 'vocab', 'encyclopedia.html')
PRE = os.path.join(ROOT, 'pre-sentence.txt')
IMGDIR = os.path.join(ROOT, 'vocab', 'images')

ENTRY_RE = re.compile(
    r'<article class="entry" style="--c:(?P<c>#[0-9A-Fa-f]{6})">'
    r'<div class="entry-main">'
    r'<h3 class="entry-word">(?P<word>.*?)</h3>'
    r'<p class="entry-sentence">(?P<sent>.*?)</p>'
    r'</div><img class="entry-image" src="(?P<src>[^"]*)" alt="(?P<alt>[^"]*)" loading="lazy" decoding="async" width="112" height="112"></article>',
    re.S)

CAT_RE = re.compile(r'<section class="category" id="cat-(?P<name>[^"]+)" style="--c:(?P<c>#[0-9A-Fa-f]{6})">'
                    r'<header class="category-head">.*?<span class="category-count">(?P<count>[^<]*)</span>'
                    r'</header><div class="entry-list">(?P<body>.*?)</div></section>', re.S)


def load_pre():
    d = {}
    for line in open(PRE, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip():
            continue
        w, _, sent = line.partition(':')
        d[w.strip()] = sent.strip()
    return d


def img_path(word):
    for ext in ('.webp', '.png', '.jpg', '.jpeg'):
        p = os.path.join(IMGDIR, word + ext)
        if os.path.exists(p):
            return 'images/' + word + ext, p
    return None, None


def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def main():
    apply = '--apply' in sys.argv
    pre = load_pre()
    s = open(ENC, encoding='utf-8').read()

    renames = {}   # 旧名 -> 新名
    sent_upd = []  # (word, old_sent, new_sent)
    to_add = []    # word

    for m in ENTRY_RE.finditer(s):
        raw = m.group('word')
        word = html.unescape(raw)
        sent = html.unescape(m.group('sent'))
        if word in pre:
            if sent != pre[word]:
                sent_upd.append((word, sent, pre[word]))
        else:
            # 尝试推测重命名：pre 里有没有同名图片对应的新词条
            found = None
            for pw in pre:
                if pw.replace('-', ' ').lower() == word.replace('-', ' ').lower():
                    found = pw
                    break
            if found:
                renames[word] = found

    enc_words = {html.unescape(m.group('word')) for m in ENTRY_RE.finditer(s)}
    pre_after = {renames.get(w, w) for w in enc_words}
    for w in pre:
        if w not in pre_after and img_path(w)[0]:
            to_add.append(w)

    print('=== 计划 ===')
    print('重命名 %d 条:' % len(renames))
    for o, n in renames.items():
        print('   %r -> %r' % (o, n))
    print('例句更新 %d 条:' % len(sent_upd))
    for w, o, n in sent_upd[:10]:
        print('   %r' % w)
    print('新增词条 %d 条:' % len(to_add))
    for w in to_add:
        print('   %r  img=%s' % (w, img_path(w)[0]))

    if not apply:
        print('\n(dry-run，加 --apply 落盘)')
        return

    shutil.copy2(ENC, ENC + '.bak')
    out = s
    # 1) 重命名 + 例句更新
    def repl_entry(m):
        raw = m.group('word')
        word = html.unescape(raw)
        new = renames.get(word, word)
        sent = pre.get(new, html.unescape(m.group('sent')))
        src = m.group('src')
        if new != word:
            p, _ = img_path(new)
            if p:
                src = p
        return ('<article class="entry" style="--c:%s"><div class="entry-main">'
                '<h3 class="entry-word">%s</h3><p class="entry-sentence">%s</p>'
                '</div><img class="entry-image" src="%s" alt="%s" loading="lazy" decoding="async" width="112" height="112"></article>'
                % (m.group('c'), esc(new), esc(sent), src, esc(new)))
    out = ENTRY_RE.sub(repl_entry, out)

    # 2) 新增词条，按分类插入并重排
    ADD_CAT = {
        'altitude': '自然地理',
        'jupiter': '自然地理',
        'hanukkah': '文化艺术',
        'chip-in': '社会关系',
        'live-life-to-the-full': '抽象概念',
        'vice-versa': '抽象概念',
        'thong': '服饰穿搭',
    }
    added = 0
    for word in to_add:
        cat = ADD_CAT.get(word, '抽象概念')
        p, _ = img_path(word)
        entry = ('<article class="entry" style="--c:%s"><div class="entry-main">'
                 '<h3 class="entry-word">%s</h3><p class="entry-sentence">%s</p>'
                 '</div><img class="entry-image" src="%s" alt="%s" loading="lazy" decoding="async" width="112" height="112"></article>')
        cm = CAT_RE.search(out)
        # 找目标分类
        for cm in CAT_RE.finditer(out):
            if cm.group('name') == cat:
                break
        if cm.group('name') != cat:
            print('!! 找不到分类', cat, '跳过', word)
            continue
        c = cm.group('c')
        body = cm.group('body')
        arts = re.findall(r'<article class="entry".*?</article>', body, re.S)
        arts.append(entry % (c, esc(word), esc(pre[word]), p, esc(word)))
        def key(a):
            return html.unescape(re.search(r'<h3 class="entry-word">(.*?)</h3>', a).group(1)).lower()
        arts.sort(key=key)
        new_body = ''.join(arts)
        new_sec = ('<section class="category" id="cat-%s" style="--c:%s">'
                   '<header class="category-head">%s<span class="category-count">%d 词</span>'
                   '</header><div class="entry-list">%s</div></section>')
        hdr = re.search(r'<header class="category-head">(.*?)<span class="category-count">', cm.group(0), re.S).group(1)
        out = out[:cm.start()] + (new_sec % (cat, c, hdr, len(arts), new_body)) + out[cm.end():]
        added += 1
        print('  + [%s] %s' % (cat, word))

    # 3) 修 thongs -> thong（已在 to_add 处理为新增，需删除旧条目）
    if 'thongs' in renames or 'thong' in renames.values():
        pass

    open(ENC, 'w', encoding='utf-8').write(out)
    print('\n已写盘，新增 %d，重命名 %d，例句更新 %d' % (added, len(renames), len(sent_upd)))
    print('备份: %s.bak' % ENC)


if __name__ == '__main__':
    main()
