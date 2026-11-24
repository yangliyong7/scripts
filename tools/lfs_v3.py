#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LFS PNG -> WebP 稳健版 v3

针对环境特征（实测）：
  - batch API 时通时不通（000/超时），但成功时很快 → 必须重试 + 缓存 href
  - 签名 href 有效 1 小时 → 存到磁盘复用，避免反复请求 batch
  - 整段下载 ~400KB 被 reset，但 HTTP Range 请求稳定 → 分片下载
  - 单张 ~4.5 分钟 → 多图并发 + 图内少分片(512KB)平衡

进度持久化: /tmp/lfs_state.json (base -> {oid,size,href,href_ts})
断点续传: 分片文件留在 /tmp/lfsseg/，重启接着下

用法: python3 tools/lfs_v3.py [--workers 6] [--seg 524288] [--limit N]
"""
import argparse, concurrent.futures as cf, json, os, re, subprocess, sys, time
import urllib.request, base64

REPO = "yangliyong7/scripts"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "vocab/images")
SEGDIR = "/tmp/lfsseg"
STATE = "/tmp/lfs_state.json"
LOG = "/tmp/lfs_v3.log"
HREF_TTL = 3000  # 50 分钟


def log(m):
    line = "%s %s" % (time.strftime("%F %T"), m)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def token():
    s = open("/root/.git-credentials-tmp").read()
    return re.search(r"x-access-token:([^@]+)@", s).group(1)


def sh(*a, **kw):
    return subprocess.run(list(a), cwd=kw.get("cwd", ROOT), capture_output=True)


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


def batch_one(oid, size, tok, tries=10):
    """单对象 batch，重试到成功。单对象比 85 个一批更容易通，且失败不影响别人"""
    url = "https://github.com/%s.git/info/lfs/objects/batch" % REPO
    basic = base64.b64encode(("x-access-token:" + tok).encode()).decode()
    body = json.dumps({"operation": "download", "transfers": ["basic"],
                       "objects": [{"oid": oid, "size": size}]}).encode()
    for t in range(tries):
        try:
            req = urllib.request.Request(url, data=body, method="POST", headers={
                "Accept": "application/vnd.git-lfs+json",
                "Content-Type": "application/vnd.git-lfs+json",
                "Authorization": "***" + basic})
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            a = (d.get("objects", [{}])[0].get("actions") or {}).get("download") or {}
            if a.get("href"):
                time.sleep(0.4)  # 轻微节流，防止 batch API 被限流
                return a["href"]
        except Exception:
            pass
        # 指数退避：限流时越等越久，避免把账号打进黑屋
        time.sleep(min(3 * (2 ** t), 60))
    return None


def get_seg(href, start, end, dest, tries=10):
    want = end - start + 1
    for t in range(tries):
        if os.path.exists(dest) and os.path.getsize(dest) == want:
            return True
        have = os.path.getsize(dest) if os.path.exists(dest) else 0
        s = start + have
        if s > end:
            s, have = start, 0
        p = dest + ".p"
        subprocess.run(["curl", "-4", "-sS", "--http1.1", "--max-time", "30",
                        "--connect-timeout", "6", "-r", "%d-%d" % (s, end), "-o", p, href],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            # 流式追加，避免把整段读进内存（16 线程同时持有会推爆 RSS）
            with open(p, "rb") as fin, open(dest, "ab" if have else "wb") as fout:
                while True:
                    buf = fin.read(65536)
                    if not buf:
                        break
                    fout.write(buf)
            os.remove(p)
        if os.path.exists(dest) and os.path.getsize(dest) == want:
            return True
        time.sleep(1 + t * 0.5)
    return False


def png_ok(p):
    """校验后立即释放图像对象，避免 PIL 缓存堆积"""
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
    r = subprocess.run(["cwebp", "-quiet", "-q", "80", "-resize", "800", "0", png, "-o", tmp], capture_output=True)
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


def save_state(st):
    json.dump(st, open(STATE, "w"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="187b140")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seg", type=int, default=524288)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    open(LOG, "w").close()
    os.makedirs(SEGDIR, exist_ok=True)
    tok = token()
    st = load_state()

    files = list_png(a.target)
    todo = []
    for name, oid, size in files:
        out = os.path.join(DST, name + ".webp")
        if os.path.exists(out) and os.path.getsize(out) > 0:
            continue
        todo.append((name, oid, size))
    if a.limit:
        todo = todo[:a.limit]
    log("START total_png=%d 待处理=%d workers=%d seg=%d" % (len(files), len(todo), a.workers, a.seg))
    if not todo:
        log("DONE 没有待处理")
        return 0

    ok = fail = 0
    t0 = time.time()
    lock = __import__("threading").Lock()

    def work(item):
        nonlocal ok, fail
        name, oid, size = item
        # 1) 拿 href（缓存优先）
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
                save_state(st)

        # 2) 分片下载（断点续传）
        segs = list(range(0, size, a.seg))
        for idx, s0 in enumerate(segs):
            e0 = min(s0 + a.seg - 1, size - 1)
            sp = os.path.join(SEGDIR, "%s.%05d" % (name, idx))
            if not get_seg(href, s0, e0, sp):
                # href 可能过期，清缓存下次重拿
                with lock:
                    st.pop(name, None); save_state(st)
                    fail += 1
                return name, "SEGFAIL@%d" % idx

        # 3) 拼装 + 校验 + 转 webp
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
                n = ok + fail
                if n % 5 == 0:
                    el = time.time() - t0
                    log("PROGRESS ok=%d fail=%d %d/%d %.2f张/分 剩余约%.1f小时"
                        % (ok, fail, n, len(todo), n / max(el, 1) * 60,
                           (len(todo) - n) / max(n / max(el, 1) * 60, 0.01) / 60))
            return name, "OK"
        finally:
            if os.path.exists(png):
                os.remove(png)

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for name, status in ex.map(work, todo):
            if status != "OK":
                log("FAIL %s %s" % (name, status))

    log("DONE ok=%d fail=%d elapsed=%.0fs webp_total=%d"
        % (ok, fail, time.time() - t0, len([x for x in os.listdir(DST) if x.endswith(".webp")])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
