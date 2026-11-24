#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断 33 张失败的 batch API 响应"""
import json, base64, re, subprocess, urllib.request, urllib.error, sys

REPO = "yangliyong7/scripts"
ROOT = "/root/.openclaw/workspace/scripts"

def token():
    return re.search(r"x-access-token:([^@]+)@", open("/root/.git-credentials-tmp").read()).group(1)

def sh(*a):
    return subprocess.run(list(a), cwd=ROOT, capture_output=True)

target = sys.argv[1] if len(sys.argv) > 1 else "187b140"
names = sys.argv[2:] or ["footage"]
tok = token()

out = sh("git", "ls-tree", "-r", target, "vocab/images/").stdout.decode()
info = {}
for line in out.splitlines():
    if not line.endswith(".png"):
        continue
    parts = line.split("\t")
    blob = parts[0].split()[2]
    name = parts[1].strip().split("/")[-1][:-4]
    t = sh("git", "cat-file", "-p", blob).stdout.decode("utf-8", "replace")
    mo = re.search(r"oid sha256:([0-9a-f]{64})", t)
    ms = re.search(r"size (\d+)", t)
    if not mo:
        # 不是 LFS 指针，是真实二进制，跳过
        continue
    if mo and ms:
        info[name] = (mo.group(1), int(ms.group(1)))

basic = base64.b64encode(("x-access-token:" + tok).encode()).decode()

for host in ["https://github.com", "https://ghproxy.net/https://github.com"]:
    url = "%s/%s.git/info/lfs/objects/batch" % (host, REPO)
    for n in names:
        if n not in info:
            print("no such png:", n); continue
        oid, size = info[n]
        body = json.dumps({"operation": "download", "transfers": ["basic"],
                           "objects": [{"oid": oid, "size": size}]}).encode()
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Accept": "application/vnd.git-lfs+json",
            "Content-Type": "application/vnd.git-lfs+json",
            "Authorization": "Basic " + basic})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            ob = d.get("objects", [{}])[0]
            err = ob.get("error")
            acts = ob.get("actions") or {}
            print("[%s] %s size=%d error=%s actions=%s" % (host, n, size, err, list(acts.keys())))
            if err:
                print("   ->", json.dumps(err)[:400])
        except urllib.error.HTTPError as e:
            print("[%s] %s HTTPError %s %s" % (host, n, e.code, e.read()[:300]))
        except Exception as e:
            print("[%s] %s EXC %s" % (host, n, e))
