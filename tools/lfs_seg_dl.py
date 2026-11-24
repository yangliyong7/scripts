#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LFS PNG -> WebP：小分片 + 断点重试版（应对 CDN 连接被 reset 的环境）

实测结论：整段连接会在 ~400KB 处被 reset，但 HTTP Range 请求能通（206）。
所以把每张图切成 256KB 的小段，每段独立重试，拼装后校验，再转 webp。
任何一段始终拿不到就放弃该图（不产出半截图）。

用法: python3 tools/lfs_seg_dl.py [--target 187b140] [--workers 8] [--seg 262144]
"""
import argparse, concurrent.futures as cf, json, os, re, subprocess, sys, tempfile, time
import urllib.request, base64

REPO = "yangliyong7/scripts"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "vocab/images")
LOG = "/tmp/lfs_seg.log"


def log(m):
    line = "%s %s" % (time.strftime("%F %T"), m)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def token():
    s = open("/root/.git-credentials-tmp").read()
    return re.search(r"x-access-token:([^@]+)@", s).group(1)


def git(*a):
    return subprocess.run(["git"] + list(a), cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace").strip()


def list_png(target):
    out = subprocess.run(["git", "ls-tree", "-r", target, "vocab/images/"], cwd=ROOT,
                         capture_output=True).stdout.decode("utf-8", "replace")
    res = []
    for line in out.splitlines():
        if not line.endswith(".png"):
            continue
        blob = line.split("\t")[0].split()[2]
        path = line.split("\t")[1]
        t = subprocess.run(["git", "cat-file", "-p", blob], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
        mo = re.search(r"oid sha256:([0-9a-f]{64})", t)
        ms = re.search(r"size (\d+)", t)
        if mo and ms:
            res.append((os.path.basename(path)[:-4], mo.group(1), int(ms.group(1))))
    return res


def batch(objs, tok):
    url = "https://github.com/%s.git/info/lfs/objects/batch" % REPO
    basic = base64.b64encode(("x-access-token:" + tok).encode()).decode()
    req = urllib.request.Request(url, data=json.dumps({
        "operation": "download", "transfers": ["basic"],
        "objects": [{"oid": o, "size": s} for o, s in objs]}).encode(),
        method="POST", headers={"Accept": "application/vnd.git-lfs+json",
                                "Content-Type": "application/vnd.git-lfs+json",
                                "Authorization": "***" + basic})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    out = {}
    for o in d.get("objects", []):
        a = (o.get("actions") or {}).get("download") or {}
        if a.get("href"):
            out[o["oid"]] = a["href"]
    return out


def get_seg(href, start, end, dest, tries=8):
    """下載 [start,end] 闭区间到 dest，失败重试，大小必须精确"""
    want = end - start + 1
    for t in range(tries):
        if os.path.exists(dest) and os.path.getsize(dest) == want:
            return True
        # 已有部分则续传
        have = os.path.getsize(dest) if os.path.exists(dest) else 0
        s = start + have
        if s > end:
            s = start
            have = 0
        subprocess.run(["curl", "-4", "-sS", "--http1.1", "--max-time", "25",
                        "--connect-timeout", "6", "-r", "%d-%d" % (s, end),
                        "-o", dest + ".p", href],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(dest + ".p"):
            with open(dest + ".p", "rb") as f:
                chunk = f.read()
            os.remove(dest + ".p")
            if chunk:
                with open(dest, "ab" if have else "wb") as f:
                    f.write(chunk)
        if os.path.exists(dest) and os.path.getsize(dest) == want:
            return True
        time.sleep(1 + t)
    return False


def png_ok(p):
    try:
        from PIL import Image
        im = Image.open(p); im.verify()
        im = Image.open(p); im.load()
        return im.size[0] > 100 and im.size[1] > 100
    except Exception:
        return False


def to_webp(png, out):
    tmp = out + ".tmp"
    r = subprocess.run(["cwebp", "-quiet", "-q", "80", "-resize", "800", "0", png, "-o", tmp], capture_output=True)
    if r.returncode == 0 and os.path.getsize(tmp) > 0:
        os.replace(tmp, out)
        return True
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="187b140")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seg", type=int, default=262144)
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 张，用于验证")
    a = ap.parse_args()
    open(LOG, "w").close()
    tok = token()
    files = list_png(a.target)
    todo = [f for f in files if not (os.path.exists(os.path.join(DST, f[0] + ".webp"))
                                    and os.path.getsize(os.path.join(DST, f[0] + ".webp")) > 0)]
    if a.limit:
        todo = todo[:a.limit]
    log("START target=%s total=%d todo=%d workers=%d seg=%d" % (a.target, len(files), len(todo), a.workers, a.seg))
    if not todo:
        return 0

    tmpd = tempfile.mkdtemp(prefix="seg_")
    ok = fail = 0
    t0 = time.time()

    def batch_retry(objs, tries=6):
        for t in range(tries):
            try:
                r = batch(objs, tok)
                if r:
                    return r
            except Exception as e:
                log("BATCH_FAIL try%d %s" % (t + 1, e))
            time.sleep(5 + t * 5)
        return {}

    hrefs = {}
    for i in range(0, len(todo), 85):
        hrefs.update(batch_retry([(x[1], x[2]) for x in todo[i:i + 85]]))
    log("hrefs=%d/%d" % (len(hrefs), len(todo)))
    if not hrefs:
        log("DONE 拿不到任何 href，退出")
        return 1

    def work(item):
        base, oid, size = item
        href = hrefs.get(oid)
        if not href:
            return base, "NOHREF"
        png = os.path.join(tmpd, base + ".png")
        try:
            if os.path.exists(png):
                os.remove(png)
            segs = list(range(0, size, a.seg))
            for idx, st in enumerate(segs):
                en = min(st + a.seg - 1, size - 1)
                if not get_seg(href, st, en, os.path.join(tmpd, "%s.%05d" % (base, idx))):
                    return base, "SEGFAIL@%d" % idx
            with open(png, "wb") as out:
                for idx in range(len(segs)):
                    p = os.path.join(tmpd, "%s.%05d" % (base, idx))
                    with open(p, "rb") as f:
                        out.write(f.read())
                    os.remove(p)
            if os.path.getsize(png) != size:
                return base, "SIZE"
            if not png_ok(png):
                return base, "BADPNG"
            if not to_webp(png, os.path.join(DST, base + ".webp")):
                return base, "WEBPFAIL"
            return base, "OK"
        finally:
            if os.path.exists(png):
                os.remove(png)

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for base, st in ex.map(work, todo):
            if st == "OK":
                ok += 1
            else:
                fail += 1
                log("FAIL %s %s" % (base, st))
            n = ok + fail
            if n % 10 == 0:
                el = time.time() - t0
                log("PROGRESS ok=%d fail=%d %d/%d %.1f张/分" % (ok, fail, n, len(todo), n / max(el, 1) * 60))

    log("DONE ok=%d fail=%d elapsed=%.0fs" % (ok, fail, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
