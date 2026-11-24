#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LFS PNG -> WebP：多轮重试版
针对 alambic CDN 连接被 reset 的环境：短超时 + 断点续传语义（完整才收）+ 多轮 + 高并发
只有 size 完全匹配且 PIL 校验通过才转 webp，绝不落半截图

用法: python3 tools/lfs_retry.py [--rounds 8] [--workers 24] [--target 187b140]
"""
import argparse, concurrent.futures as cf, json, os, re, signal, subprocess, sys, tempfile, time
import urllib.request, base64

REPO = "yangliyong7/scripts"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "vocab/images")
LOG = "/tmp/lfs_retry.log"


def log(msg):
    line = "%s %s" % (time.strftime("%F %T"), msg)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def token():
    s = open("/root/.git-credentials-tmp").read().strip()
    return re.search(r"x-access-token:([^@]+)@", s).group(1)


def g(*a):
    return subprocess.run(["git"] + list(a), cwd=ROOT, capture_output=True).stdout.decode(
        "utf-8", "replace").strip()


def g_bin(*a):
    return subprocess.run(["git"] + list(a), cwd=ROOT, capture_output=True).stdout


def g_text(*a):
    """只用于返回文本的 git 命令；cat-file -p 可能吐出二进制，单独走 g_bin"""
    return subprocess.run(["git"] + list(a), cwd=ROOT, capture_output=True).stdout.decode(
        "utf-8", "replace").strip()


def list_png(target):
    out = g("ls-tree", "-r", target, "vocab/images/")
    files = []
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2 or not parts[1].endswith(".png"):
            continue
        path = parts[1]
        oid_blob = parts[0].split()[2]
        blob = g("cat-file", "-p", oid_blob)
        mo = re.search(r"oid sha256:([0-9a-f]{64})", blob)
        ms = re.search(r"size (\d+)", blob)
        if mo and ms:
            files.append((os.path.basename(path)[:-4], mo.group(1), int(ms.group(1))))
    return files


def batch(objs, tok):
    url = "https://github.com/%s.git/info/lfs/objects/batch" % REPO
    basic = base64.b64encode(("x-access-token:" + tok).encode()).decode()
    req = urllib.request.Request(
        url,
        data=json.dumps({"operation": "download", "transfers": ["basic"],
                         "objects": [{"oid": o, "size": s} for o, s in objs]}).encode(),
        method="POST",
        headers={"Accept": "application/vnd.git-lfs+json",
                 "Content-Type": "application/vnd.git-lfs+json",
                 "Authorization": "Basic " + basic})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    out = {}
    for o in d.get("objects", []):
        act = (o.get("actions") or {}).get("download") or {}
        if act.get("href"):
            out[o["oid"]] = act["href"]
    return out


def fetch(href, dest, maxtime=45):
    p = subprocess.Popen(
        ["curl", "-4", "-sS", "--http1.1", "--max-time", str(maxtime),
         "--connect-timeout", "8", "-o", dest, href],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
    try:
        p.wait(timeout=maxtime + 10)
        return True
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass
        return False


def png_ok(path):
    try:
        from PIL import Image
        im = Image.open(path); im.verify()
        im = Image.open(path); im.load()
        return im.size[0] > 100 and im.size[1] > 100
    except Exception:
        return False


def to_webp(png, out):
    tmp = out + ".tmp"
    r = subprocess.run(["cwebp", "-quiet", "-q", "80", "-resize", "800", "0", png, "-o", tmp],
                       capture_output=True)
    if r.returncode == 0 and os.path.getsize(tmp) > 0:
        os.replace(tmp, out); return True
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="187b140")
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--maxtime", type=int, default=45)
    a = ap.parse_args()
    open(LOG, "w").close()
    tok = token()
    files = list_png(a.target)
    todo = [f for f in files if not (os.path.exists(os.path.join(DST, f[0] + ".webp"))
                                    and os.path.getsize(os.path.join(DST, f[0] + ".webp")) > 0)]
    log("START target=%s total=%d todo=%d workers=%d" % (a.target, len(files), len(todo), a.workers))
    if not todo:
        return 0

    tmpdir = tempfile.mkdtemp(prefix="lfsr_")
    ok = 0
    t0 = time.time()

    for rd in range(1, a.rounds + 1):
        if not todo:
            break
        # 每轮重新拿 href（签名 1 小时有效，但重拿更稳）
        hrefs = {}
        for i in range(0, len(todo), 85):
            try:
                hrefs.update(batch([(x[1], x[2]) for x in todo[i:i + 85]], tok))
            except Exception as e:
                log("BATCH_FAIL rd=%d idx=%d %s" % (rd, i, e))
        log("ROUND%d start todo=%d hrefs=%d" % (rd, len(todo), len(hrefs)))

        def work(item):
            base, oid, size = item
            href = hrefs.get(oid)
            if not href:
                return (base, "NOHREF")
            png = os.path.join(tmpdir, base + ".png")
            try:
                if not fetch(href, png, a.maxtime):
                    return (base, "DLFAIL")
                got = os.path.getsize(png)
                if got != size:
                    return (base, "SIZE %d/%d" % (got, size))
                if not png_ok(png):
                    return (base, "BADPNG")
                out = os.path.join(DST, base + ".webp")
                if not to_webp(png, out):
                    return (base, "WEBPFAIL")
                return (base, "OK")
            finally:
                if os.path.exists(png):
                    os.remove(png)

        remaining = []
        with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
            for (base, st), item in zip(ex.map(work, todo), todo):
                if st == "OK":
                    ok += 1
                else:
                    remaining.append(item)
        done_round = len(todo) - len(remaining)
        todo = remaining
        el = time.time() - t0
        log("ROUND%d end ok_round=%d remain=%d total_ok=%d %.1f张/分 "
            % (rd, done_round, len(todo), ok, ok / max(el, 1) * 60))
        if not todo:
            break
        time.sleep(20)

    try:
        os.rmdir(tmpdir)
    except Exception:
        pass
    log("DONE ok=%d remain=%d elapsed=%.0fs" % (ok, len(todo), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
