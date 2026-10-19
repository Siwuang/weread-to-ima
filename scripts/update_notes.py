#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信读书笔记增量更新 v4：删自动块+想法碎片，保留真用户内容，循环分批"""
import json, uuid, subprocess, os, time

for _k in ("IMA_OPENAPI_CLIENTID", "IMA_OPENAPI_APIKEY"):
    if not os.environ.get(_k):
        print(f"[!] 缺少环境变量: {_k}")
        print(f'[!] 请先设置： export {_k}="你的值"')
        raise SystemExit(1)

HEADERS = [
    "-H", f"ima-openapi-clientid: {os.environ['IMA_OPENAPI_CLIENTID']}",
    "-H", f"ima-openapi-apikey: {os.environ['IMA_OPENAPI_APIKEY']}",
    "-H", "Content-Type: application/json",
]

def api(endpoint, body, retries=5):
    for attempt in range(retries):
        cmd = ["curl", "-s", "--max-time", "60", "-X", "POST", f"https://ima.qq.com/openapi/note/v1/{endpoint}"] + HEADERS + ["-d", json.dumps(body, ensure_ascii=False)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return json.loads(r.stdout)
        except Exception:
            print(f"  网络波动，重试 {attempt+1}/{retries}...")
            time.sleep(3)
    raise RuntimeError("多次重试失败")

def extract_excerpt(md):
    start_marker = "## 📖 读书时 · 划线摘录"
    end_marker = "## 🧠 读书后 · 思考沉淀"
    s = md.find(start_marker)
    e = md.find(end_marker)
    if s == -1 or e == -1 or e <= s:
        return None
    return md[s + len(start_marker):e].strip()

def build_source_texts(reviews_file, marks_file):
    """收集微信读书想法全文 + 划线原文，用于识别多行内容拆分产生的碎片块"""
    texts = []
    try:
        d = json.load(open(reviews_file, encoding="utf-8"))
        for rv in d.get("reviews", []) or []:
            r = rv.get("review", rv)
            c = r.get("content", "").strip()
            if c:
                texts.append(c)
    except Exception:
        pass
    try:
        d = json.load(open(marks_file, encoding="utf-8"))
        for m in d.get("updated", []) or []:
            if m.get("type", 1) == 1:
                c = m.get("markText", "").strip()
                if c:
                    texts.append(c)
    except Exception:
        pass
    return texts

def is_auto_or_fragment(content, source_texts, excerpt):
    """判断是否为自动生成的划线/想法块或碎片（多行内容被 ima 拆分的续行）"""
    c = content.strip()
    if not c:
        return False
    # 自动格式块
    if c.startswith("> 📌") or c.startswith("> ⏱") or c.startswith("> 💭") or c.startswith("### 📄"):
        return True
    if "划线共" in c and "想法" in c and c.startswith(">"):
        return True
    # 碎片识别：内容出现在新摘录中，或完整包含于某条划线和想法中
    if len(c) >= 4:
        if excerpt and c in excerpt:
            return True
        for t in source_texts:
            if c in t:
                return True
    return False

def batch_update(note_id, user_request_id, delete_ids, append_block_id, excerpt):
    total = len(delete_ids)
    i = 0
    batch_no = 0
    while i < total:
        batch = delete_ids[i:i+95]
        i += 95
        batch_no += 1
        ops = [{"block_id": b, "action": 2} for b in batch]
        if i >= total:
            ops.append({"block_id": append_block_id, "action": 3, "new_content": excerpt})
            if len(ops) > 100:
                r = api("update_note", {"note_id": note_id, "user_request_id": user_request_id, "updates": ops[:95]})
                print(f"  批{batch_no}a(删{len(ops[:95])}): code={r.get('code')}")
                r2 = api("update_note", {"note_id": note_id, "user_request_id": user_request_id, "updates": ops[95:]})
                results = r2.get("data", {}).get("results", [])
                fails = [x for x in results if not x.get("success")]
                print(f"  批{batch_no}b(删+追加): code={r2.get('code')} 失败={len(fails)}")
                continue
        r = api("update_note", {"note_id": note_id, "user_request_id": user_request_id, "updates": ops})
        results = r.get("data", {}).get("results", [])
        fails = [x for x in results if not x.get("success")]
        print(f"  批{batch_no}: code={r.get('code')} 操作={len(ops)} 失败={len(fails)}")
        if fails:
            print("   ", fails[:2])

def update_incremental(note_id, md_file, name, reviews_file, marks_file=None):
    new_md = open(md_file, encoding="utf-8").read()
    if marks_file is None:
        marks_file = reviews_file.replace("_reviews", "_marks")
    source_texts = build_source_texts(reviews_file, marks_file)
    d = api("export_note_blocks", {"note_id": note_id})
    blocks = d.get("data", {}).get("blocks", [])
    start_idx = end_idx = -1
    for i, b in enumerate(blocks):
        content = b.get("content", "")
        if "读书时 · 划线摘录" in content and start_idx == -1:
            start_idx = i
        if "读书后 · 思考沉淀" in content:
            end_idx = i
    excerpt = extract_excerpt(new_md)
    if start_idx == -1 or end_idx == -1 or excerpt is None:
        print(f"{name}: ⚠️ 定位失败，跳过（不覆盖）")
        return
    delete_ids = []
    kept = 0
    for b in blocks[start_idx+1:end_idx]:
        if b.get("editable") and is_auto_or_fragment(b.get("content", ""), source_texts, excerpt):
            delete_ids.append(b["block_id"])
        else:
            kept += 1
    start_block_id = blocks[start_idx]["block_id"]
    print(f"{name}: 删除自动块+想法碎片 {len(delete_ids)} 个，保留真用户内容块 {kept} 个")
    user_request_id = str(uuid.uuid4())
    batch_update(note_id, user_request_id, delete_ids, start_block_id, excerpt)

STATE_FILE = os.path.join(WORKDIR, "weread_state.json")


def load_state():
    """读取上次同步时的 sort 快照"""
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def load_sort_map():
    """从 weread_notebooks.json 取 {bookId: sort}，即书架变化指纹"""
    try:
        nb = json.load(open(os.path.join(WORKDIR, "weread_notebooks.json"), encoding="utf-8"))
        return {str(b["bookId"]): b.get("sort") for b in nb.get("books", [])}
    except Exception:
        return {}


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv          # --force 可强制全量更新

    # 从 config.json 读取：(note_id, md文件, 书名, 想法json, bookId)
    notes = []
    for n in CFG.get("notes", []):
        b = next((x for x in CFG["weread"]["books"] if x["abbr"] == n["abbr"]), {})
        notes.append((
            n["note_id"],
            os.path.join(WORKDIR, n["md_file"]),
            n.get("name", n["abbr"]),
            f"weread_{n['abbr']}_reviews.json",
            b.get("book_id", ""),
        ))

    sort_map = load_sort_map()
    if not sort_map:
        print("⚠️ 读不到 weread_notebooks.json，退化为全量更新")
    state = load_state()
    changed, skipped = [], []
    for nid, mdf, nm, rf, bid in notes:
        cur, prev = sort_map.get(bid), state.get(bid)
        if not force and sort_map and cur is not None and prev is not None and cur == prev:
            skipped.append(nm)
            continue
        changed.append((nid, mdf, nm, rf, bid, cur))

    print(f"【变化检测】有更新 {len(changed)} 本 / 无更新跳过 {len(skipped)} 本")
    if skipped:
        print("  跳过:", "、".join(skipped))
    if not changed:
        print("本次没有任何书籍更新，无需操作。")

    for nid, mdf, nm, rf, bid, cur in changed:
        print(f"\n=== 更新《{nm}》 ===")
        update_incremental(nid, mdf, nm, rf)
        if cur is not None:
            state[bid] = cur
    save_state(state)
