#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 LFS 拉取 vocab/images/*.png（远端 187b140 那批 800 张）直接转 webp，不落盘 PNG。
可复用：和 2026-08 / 2026-11-21 那两次崩溃修复同一套套路。

核心套路（为什么不用 git lfs pull/smudge）：
  1. 指针文件里读到精确 oid + size  → POST /objects/batch 拿签名下载 href
  2. batch 一次最多 ~90 个对象，超了会返回错误 / 空链接（历史大坑）
  3. 直连 href（github-cloud alambic），不要再套 ghproxy，否则 403
  4. 每个下载用独立进程组 + 硬超时，防单连接挂死阻塞整批（历史大坑）
  5. 下载完立即 PIL 校验（verify + load），残缺就丢，避免 0 字节/截断静默入库
  6. 转 cwebp 后立刻删临时 PNG，峰值只占一张图的磁盘

用法:
  python3 tools/lfs_png2webp.py --target 187b140 [--workers 12] [--batch 85] [--dry]
"""
import argparse, concurrent.futures as cf, json, os, re, signal, subprocess, sys, tempfile, time
import urllib.request, base64

REPO = "yangliyong7/scripts"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "vocab/images")
LOG = "/tmp/lfs_png2webp.log"


def log(msg):
    line = "%s %s" % (time.strftime("%F %T"), msg)
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def token():
    try:
        s = open("/root/.git-credentials-tmp").read().strip()
        m = re.search(r"x-access-token:([^@]+)@", s)
        if m:
            return m.group(1)
    except Exception:
        pass
    return os.environ.get("GH_TOKEN", "")


def g(*args):
    r = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip()


def list_png(target):
    """返回 [(路径, oid, size)] —— 从 git 读取指针文件内容"""
    out = g("ls-tree", "-r", "--long", target, "vocab/images/")
    files = []
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        meta, path = parts[:3], parts[3]
        if not path.endswith(".png"):
            continue
        oid = meta[2]
        try:
            blob = g("cat-file", "-p", oid)
        except Exception:
            continue
        if "git-lfs.github.com/spec/v1" not in blob:
            continue
        mo = re.search(r"oid sha256:([0-9a-f]{64})", blob)
        ms = re.search(r"size (\d+)", blob)
        if mo and ms:
            files.append((path, mo.group(1), int(ms.group(1))))
    return files


def batch(objs, tok):
    """一次 batch 拿 href，objs=[(oid,size)]，调用方负责每批<=90"""
    # URL 里绝不能放 token：pat 含下划线，urlopen 会把它当端口解析 -> nonnumeric port
    # 认证走 Basic header（git-lfs 的标准做法）
    url = "https://github.com/%s.git/info/lfs/objects/batch" % REPO
    payload = json.dumps({
        "operation": "download",
        "transfers": ["basic"],
        "objects": [{"oid": o, "size": s} for o, s in objs],
    }).encode()
    basic = base64.b64encode(("x-access-token:" + tok).encode()).decode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Accept": "application/vnd.git-lfs+json",
        "Content-Type": "application/vnd.git-lfs+json",
        "Authorization": "Basic " + basic,
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    out = {}
    for o in data.get("objects", []):
        act = (o.get("actions") or {}).get("download") or {}
        if act.get("href"):
            out[o["oid"]] = act["href"]
    return out


def fetch_href(href, dest, timeout=180):
    """独立进程组 + 硬超时，防挂死"""
    p = subprocess.Popen(
        ["curl", "-sSL", "--retry", "2", "--connect-timeout", "20", "--max-time", str(timeout),
         "-o", dest, href],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
    try:
        return p.wait(timeout=timeout + 20) == 0
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass
        return False


def png_ok(path):
    try:
        from PIL import Image
        im = Image.open(path)
        im.verify()
        im = Image.open(path)
        im.load()
        return im.size[0] > 50 and im.size[1] > 50
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="187b140")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--batch", type=int, default=85, help="batch API 每批对象数，>90 会失效")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    open(LOG, "w").close()
    tok = token()
    if not tok:
        log("FATAL 拿不到 token")
        return 1

    files = list_png(a.target)
    todo = []
    skip = 0
    for path, oid, size in files:
        base = os.path.basename(path)[:-4]
        out = os.path.join(DST, base + ".webp")
        if os.path.exists(out) and os.path.getsize(out) > 0:
            skip += 1
            continue
        todo.append((path, base, oid, size))
    log("START target=%s total_png=%d 已有webp跳过=%d 待处理=%d workers=%d"
        % (a.target, len(files), skip, len(todo), a.workers))
    if a.dry:
        for t in todo[:20]:
            log("DRY %s size=%d" % (t[0], t[3]))
        return 0

    ok = fail = 0
    tmpdir = tempfile.mkdtemp(prefix="lfspng_")
    t0 = time.time()

    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        try:
            hrefs = batch([(c[2], c[3]) for c in chunk], tok)
        except Exception as e:
            log("BATCH_FAIL idx=%d err=%s" % (i, e))
            fail += len(chunk)
            continue
        log("BATCH idx=%d n=%d hrefs=%d" % (i, len(chunk), len(hrefs)))

        def work(c):
            path, base, oid, size = c
            href = hrefs.get(oid)
            if not href:
                return (base, "NOHREF")
            png = os.path.join(tmpdir, base + ".png")
            try:
                if not fetch_href(href, png):
                    return (base, "DLFAIL")
                if os.path.getsize(png) != size:
                    return (base, "SIZEMISMATCH %d!=%d" % (os.path.getsize(png), size))
                if not png_ok(png):
                    return (base, "BADPNG")
                out = os.path.join(DST, base + ".webp")
                if not to_webp(png, out):
                    return (base, "WEBPFAIL")
                return (base, "OK")
            finally:
                if os.path.exists(png):
                    os.remove(png)

        with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
            for base, st in ex.map(work, chunk):
                if st == "OK":
                    ok += 1
                else:
                    fail += 1
                    log("FAIL %s %s" % (base, st))
        el = time.time() - t0
        log("PROGRESS ok=%d fail=%d done=%d/%d %.1f张/分"
            % (ok, fail, ok + fail, len(todo), (ok + fail) / max(el, 1) * 60))

    try:
        os.rmdir(tmpdir)
    except Exception:
        pass
    log("DONE ok=%d fail=%d webp_total=%d elapsed=%.0fs"
        % (ok, fail, len([x for x in os.listdir(DST) if x.endswith(".webp")]), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
