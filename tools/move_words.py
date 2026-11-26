#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 encyclopedia.html 中的词条在分类之间移动。
用法: python3 tools/move_words.py word1=目标分类 word2=目标分类 ...
      加 --dry-run 只预演
"""
import re, sys, html, shutil, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENC = os.path.join(ROOT, 'vocab', 'encyclopedia.html')

SEC_RE = re.compile(
    r'<section class="category" id="cat-(?P<name>[^"]+)" style="--c:(?P<c>#[0-9A-Fa-f]{6})">'
    r'(?P<header><header class="category-head">.*?</header>)'
    r'<div class="entry-list">(?P<body>.*?)</div></section>', re.S)
ART_RE = re.compile(r'<article class="entry".*?</article>', re.S)


def word_of(art):
    m = re.search(r'<h3 class="entry-word">(.*?)</h3>', art)
    return html.unescape(m.group(1)) if m else None


def rebuild(sec, body, arts):
    n = len(arts)
    hdr = re.sub(r'<span class="category-count">[^<]*</span>',
                 '<span class="category-count">%d 词</span>' % n, sec.group('header'))
    return ('<section class="category" id="cat-%s" style="--c:%s">%s'
            '<div class="entry-list">%s</div></section>'
            % (sec.group('name'), sec.group('c'), hdr, ''.join(arts)))


def main():
    dry = '--dry-run' in sys.argv
    moves = {}
    for a in sys.argv[1:]:
        if a.startswith('--'):
            continue
        w, _, cat = a.partition('=')
        moves[w.strip()] = cat.strip()
    if not moves:
        print('用法: move_words.py word=分类 ...')
        return

    s = open(ENC, encoding='utf-8').read()
    secs = list(SEC_RE.finditer(s))

    # 收集所有分类的条目
    data = {}
    for m in secs:
        data[m.group('name')] = {'m': m, 'arts': ART_RE.findall(m.group('body'))}

    # 定位待移动条目
    todo = []
    for w, target in moves.items():
        if target not in data:
            print('!! 目标分类不存在:', target)
            return
        found = None
        for cat, d in data.items():
            for art in d['arts']:
                if word_of(art) == w:
                    found = (cat, art)
                    break
            if found:
                break
        if not found:
            print('!! 找不到词条:', w)
            return
        if found[0] == target:
            print('   %-10s 已在 %s，跳过' % (w, target))
            continue
        todo.append((w, found[0], target, found[1]))

    cat_color = {c: d['m'].group('c') for c, d in data.items()}

    for w, src, dst, art in todo:
        # 从源分类移除
        data[src]['arts'] = [a for a in data[src]['arts'] if word_of(a) != w]
        # 改写条目色为目分类色
        newart = re.sub(r'style="--c:#[0-9A-Fa-f]{6}"',
                        'style="--c:%s"' % cat_color[dst], art, count=1)
        data[dst]['arts'].append(newart)
        print('   %-10s %s -> %s' % (w, src, dst))

    # 目标分类按字母重排
    for w, src, dst, art in todo:
        arts = data[dst]['arts']
        arts.sort(key=lambda a: (word_of(a) or '').lower())

    print('\n=== 变更后计数 ===')
    for c in sorted({src for _, src, _, _ in todo} | {dst for _, _, dst, _ in todo}):
        print('   %-8s %d 词' % (c, len(data[c]['arts'])))

    if dry:
        print('\n(dry-run，加 --apply 落盘)')
        return

    shutil.copy2(ENC, ENC + '.bak')
    out = s
    # 从后往前替换，避免位置漂移
    for m in reversed(secs):
        name = m.group('name')
        out = out[:m.start()] + rebuild(m, m.group('body'), data[name]['arts']) + out[m.end():]
    open(ENC, 'w', encoding='utf-8').write(out)
    os.remove(ENC + '.bak')
    print('\n已写盘')


if __name__ == '__main__':
    main()
