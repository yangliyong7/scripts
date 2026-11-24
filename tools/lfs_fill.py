#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补漏 33 张：只处理 <target> 中还没有 webp 的词
比 v3 更保守：workers=2、批次间 sleep、href 双通道（github + ghproxy）、退避更长
用法: python3 tools/lfs_fill.py [--target 187b140] [--workers 2] [--limit N]
日志: /tmp/lfs_fill.log
"""
import argparse, concurrent.futures as cf, json, os, re, subprocess, sys, time, threading
import urllib.request, urllib.error, base64

REPO = "yangliyong7/scripts"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "vocab/images")
SEGDIR = "/tmp/lfsseg_fill"
STATE = "/tmp/lfs_fill_state.json"
LOG = "/tmp/lfs_fill.log"
HREF_TTL = 2400
HOSTS = ["https://github.com", "https://ghproxy.net/https://github.com"]

_fh = open(LOG, "a")


def log(m):
    line = "%s %s" % (time.strftime("%F %T"), m)
    _fh.write(line + "\n")
    _fh.flush()
    print(line, flush=True)


def token():
    return re.search(r"x-access-token:([^@]+)@", open("/root/.git-credentials-tmp").read()).group(1)


def sh(*a):
    return subprocess.run(list(a), cwd=ROOT, capture_output=True)


def list_png(target):
    out = sh("git", "ls-tree", "-r", target, "vocab/images/").stdout.decode("utf-8", "replace")
    res = []
    for line in out.splitlines():
        if not line.endswith(".png"):
            continue
        parts = line.split("\t")
        blob = parts[0].split()[2]
        name = os.path.basename(parts[1])[:-4]
        t = sh("git", "cat-file", "-p", blob).stdout.decode("utf-8", "replace")
        mo = re.search(r"oid sha256:([0-9a-f]{64})", t)
        ms = re.search(r"size (\d+)", t)
        if mo and ms:
            res.append((name, mo.group(1), int(ms.group(1))))
    return res


def batch_one(oid, size, tok, tries=12):
    basic = base64.b64encode(("x-access-token:" + tok).encode()).decode()
    body = json.dumps({"operation": "download", "transfers": ["basic"],
                       "objects": [{"oid": oid, "size": size}]}).encode()
    for t in range(tries):
        host = HOSTS[t % len(HOSTS)] if t >= 2 else HOSTS[0]
        url = "%s/%s.git/info/lfs/objects/batch" % (host, REPO)
        try:
            req = urllib.request.Request(url, data=body, method="POST", headers={
                "Accept": "application/vnd.git-lfs+json",
                "Content-Type": "application/vnd.git-lfs+json",
                "Authorization": "Basic " + basic})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            ob = (d.get("objects") or [{}])[0]
            a = (ob.get("actions") or {}).get("download") or {}
            if a.get("href"):
                time.sleep(1.2)
                return a["href"]
            if ob.get("error"):
                log("  BATCH_ERR %s" % json.dumps(ob["error"])[:200])
        except Exception as e:
            log("  BATCH_TRY%d(%s) %s" % (t + 1, host.split("//")[1][:14], type(e).__name__))
        time.sleep(min(4 * (1.6 ** t), 90))
    return None


def get_seg(href, start, end, dest, tries=12):
    want = end - start + 1
    for t in range(tries):
        have = os.path.getsize(dest) if os.path.exists(dest) else 0
        if have == want:
            return True
        s = start + have
        if s > end:
            s, have = start, 0
        p = dest + ".p"
        subprocess.run(["curl", "-4", "-sS", "--http1.1", "--max-time", "45",
                        "--connect-timeout", "8", "-r", "%d-%d" % (s, end), "-o", p, href],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            with open(p, "rb") as fin, open(dest, "ab" if have else "wb") as fout:
                while True:
                    buf = fin.read(65536)
                    if not buf:
                        break
                    fout.write(buf)
            os.remove(p)
        if os.path.exists(dest) and os.path.getsize(dest) == want:
            return True
        time.sleep(2 + t * 1.5)
    return False


def png_ok(p):
    try:
        from PIL import Image
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            im.load()
            ok = im.size[0] > 100 and im.size[1] > 100
            im.close()
        import gc
        gc.collect()
        return ok
    except Exception:
        return False


def to_webp(png, out):
    tmp = out + ".tmp"
    r = subprocess.run(["cwebp", "-quiet", "-q", "80", "-resize", "800", "0", png, "-o", tmp],
                       capture_output=True)
    if r.returncode == 0 and os.path.getsize(tmp) > 0:
        os.replace(tmp, out)
        return True
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="187b140")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seg", type=int, default=1048576)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(SEGDIR, exist_ok=True)
    tok = token()
    st = load_state()

    files = list_png(a.target)
    todo = [(n, o, s) for n, o, s in files
            if not (os.path.exists(os.path.join(DST, n + ".webp"))
                    and os.path.getsize(os.path.join(DST, n + ".webp")) > 0)]
    if a.limit:
        todo = todo[:a.limit]
    log("START total_png=%d 待补=%d workers=%d seg=%d" % (len(files), len(todo), a.workers, a.seg))
    if not todo:
        log("DONE 无待补")
        return 0

    ok = fail = 0
    t0 = time.time()
    lock = threading.Lock()
    failed = []

    def work(item):
        nonlocal ok, fail
        name, oid, size = item
        href = None
        with lock:
            e = st.get(name)
            if e and e.get("oid") == oid and e.get("href") and time.time() - e.get("ts", 0) < HREF_TTL:
                href = e["href"]
        if not href:
            href = batch_one(oid, size, tok)
            if not href:
                with lock:
                    fail += 1
                return name, "NOHREF"
            with lock:
                st[name] = {"oid": oid, "size": size, "href": href, "ts": time.time()}
                json.dump(st, open(STATE, "w"))

        segs = list(range(0, size, a.seg))
        for idx, s0 in enumerate(segs):
            e0 = min(s0 + a.seg - 1, size - 1)
            sp = os.path.join(SEGDIR, "%s.%05d" % (name, idx))
            if not get_seg(href, s0, e0, sp):
                with lock:
                    st.pop(name, None)
                    json.dump(st, open(STATE, "w"))
                    fail += 1
                return name, "SEGFAIL@%d" % idx

        png = os.path.join(SEGDIR, name + ".png")
        with open(png, "wb") as out:
            for idx in range(len(segs)):
                sp = os.path.join(SEGDIR, "%s.%05d" % (name, idx))
                with open(sp, "rb") as f:
                    while True:
                        buf = f.read(65536)
                        if not buf:
                            break
                        out.write(buf)
                os.remove(sp)
        try:
            if os.path.getsize(png) != size:
                with lock:
                    fail += 1
                return name, "SIZEBAD"
            if not png_ok(png):
                with lock:
                    fail += 1
                return name, "BADPNG"
            if not to_webp(png, os.path.join(DST, name + ".webp")):
                with lock:
                    fail += 1
                return name, "WEBPFAIL"
            with lock:
                ok += 1
                log("OK %s (%.0fKB) [%d/%d]" % (name, size / 1024, ok + fail, len(todo)))
            return name, "OK"
        finally:
            if os.path.exists(png):
                os.remove(png)

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for name, status in ex.map(work, todo):
            if status != "OK":
                log("FAIL %s %s" % (name, status))
                failed.append((name, status))

    log("DONE ok=%d fail=%d elapsed=%.0fs webp_total=%d"
        % (ok, fail, time.time() - t0, len([x for x in os.listdir(DST) if x.endswith(".webp")])))
    if failed:
        log("STILL_FAILED %s" % ",".join("%s(%s)" % f for f in failed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
