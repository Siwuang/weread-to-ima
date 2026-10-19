#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_weread.py —— 拉取微信读书划线 / 想法 / 书籍信息 / 章节目录（配置驱动版）

用法：
    python3 fetch_weread.py              # 拉取 config.json 里全部书
    python3 fetch_weread.py fq nwe       # 只拉指定 abbr 的书

输出：data/weread_<abbr>_{marks,reviews,info,chapters}.json
"""
import json
import os
import sys
import time
import urllib.request

# 让脚本能 import 项目根目录的 config_loader
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import load_config, require_env

cfg = load_config()
WD = cfg["workdir"]
API_KEY = require_env(cfg["weread"]["api_key_env"])
URL = "https://i.weread.qq.com/api/agent/gateway"
VER = cfg["weread"].get("skill_version", "1.0.4")

want = set(sys.argv[1:])
books = [b for b in cfg["weread"]["books"] if not want or b["abbr"] in want]
if not books:
    print("[!] 没有匹配的书籍，检查 config.json 的 abbr")
    sys.exit(1)


def call(body, retries=5):
    """带重试的 API 调用"""
    for attempt in range(retries):
        req = urllib.request.Request(
            URL,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"  网络波动({e})，重试 {attempt + 1}/{retries}...")
            time.sleep(3)
    raise RuntimeError("多次重试失败")


def save(name, data):
    path = os.path.join(WD, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return path


upgrade_stop = False
for b in books:
    abbr, bookid = b["abbr"], b["book_id"]
    print(f"=== {abbr} ({bookid}) {b.get('title', '')} ===")
    jobs = [
        ("marks",    {"api_name": "/book/bookmarklist", "bookId": bookid}),
        # ⚠️ count 必须传 100，否则会丢旧想法
        ("reviews",  {"api_name": "/review/list/mine", "bookid": bookid, "count": 100}),
        ("info",     {"api_name": "/book/info", "bookId": bookid}),
        ("chapters", {"api_name": "/book/chapterinfo", "bookId": bookid}),
    ]
    for kind, body in jobs:
        body["skill_version"] = VER
        try:
            data = call(body)
        except Exception as e:
            print(f"  {kind}: 失败 {e}")
            continue
        if "upgrade_info" in data:
            print("!!! 出现 upgrade_info（Skill 需要升级），立即停止")
            print(json.dumps(data.get("upgrade_info"), ensure_ascii=False))
            upgrade_stop = True
            break
        save(f"weread_{abbr}_{kind}.json", data)
        ec = data.get("errcode")
        print(f"  {kind}: errcode={ec}")
        if kind == "marks":
            print(f"    划线章节={len(data.get('chapters', []) or [])}")
        if kind == "reviews":
            print(f"    想法={len(data.get('reviews', []) or [])} total={data.get('totalCount')}")
    if upgrade_stop:
        break

print("DONE")
