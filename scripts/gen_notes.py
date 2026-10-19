#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信读书笔记固定模板生成器 v4（章节目录序 + 划线文中序 + 想法去重 + 多书）"""
import json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import load_config

CFG = load_config()
WORKDIR = CFG["workdir"]

# 核心观点从 core_views.json 加载（个人定制的摘要，可留空）
_CV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core_views.json")
try:
    CORE_VIEWS = {k: v for k, v in json.load(open(_CV_PATH, encoding="utf-8")).items() if not k.startswith("_")}
except Exception:
    CORE_VIEWS = {}

def load(name):
    with open(os.path.join(WORKDIR, name), "r", encoding="utf-8") as f:
        return json.load(f)

def ts2date(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return ""

def add_review_lines(lines, content):
    """一条想法只有一个 💭：首段带 💭 标记，后续换行原样保留、不加任何前缀"""
    paras = [p.strip() for p in str(content).split("\n")]
    paras = [p for p in paras if p]
    if not paras:
        return
    lines.append(f"> 💭 {paras[0]}")
    for para in paras[1:]:
        lines.append(para)

def range_start(rng):
    try:
        return int(str(rng).split("-")[0])
    except Exception:
        return 0


def build_note(marks_file, reviews_file, info_file, chapters_file, book_display_name, chapter_fallback="全文"):
    marks = load(marks_file)
    reviews_data = load(reviews_file)
    info = load(info_file)
    chapters_info = load(chapters_file)

    book = marks.get("book", {})
    if not book:
        book = info if isinstance(info, dict) and "title" in info else {}
    title = book.get("title", book_display_name)
    author = book.get("author", "")
    translator = book.get("translator", "")
    intro = info.get("intro", "") or book.get("intro", "")
    publish_time = info.get("publishTime", "") or book.get("publishTime", "")
    isbn = info.get("isbn", "") or book.get("isbn", "")
    category = info.get("category", "")
    publisher = info.get("publisher", "") or book.get("publisher", "")
    deep_link = info.get("deepLink", "") or book.get("deepLink", "")
    book_id = book.get("bookId", "")

    chapter_order_map = {}
    for ch in (chapters_info.get("chapters", []) or []):
        chapter_order_map[str(ch["chapterUid"])] = {
            "idx": ch.get("chapterIdx", 9999),
            "title": ch.get("title", ""),
        }

    marks_list = [m for m in marks.get("updated", []) if m.get("type", 1) == 1]
    chapters_map = {ch["chapterUid"]: ch.get("title", "") for ch in (marks.get("chapters", []) or [])}

    reviews = []
    seen_reviews = set()
    for rv in (reviews_data.get("reviews", []) or []):
        r = rv.get("review", rv)
        item = {
            "content": r.get("content", "").strip(),
            "abstract": r.get("abstract", "").strip(),
            "range": r.get("range", ""),
            "chapterUid": r.get("chapterUid", ""),
            "chapterName": r.get("chapterName", ""),
            "createTime": r.get("createTime", 0),
        }
        dedup_key = (item["range"], item["content"])
        if item["content"] and dedup_key in seen_reviews:
            continue
        seen_reviews.add(dedup_key)
        reviews.append(item)

    chapters_entries = {}
    chapter_order = []

    def get_or_create_chapter(uid, name):
        key = str(uid) if uid else f"rv-{len(chapter_order)}"
        if key not in chapters_entries:
            chapters_entries[key] = {"name": name, "entries": []}
            chapter_order.append(key)
        return key

    for m in marks_list:
        uid = m.get("chapterUid", "")
        cname = chapters_map.get(uid, "") or chapter_order_map.get(str(uid), {}).get("title", "") or chapter_fallback
        key = get_or_create_chapter(uid, cname)
        entry = {"kind": "mark", "mark": m, "reviews": []}
        rng = m.get("range", "")
        for rv in reviews:
            if rv["range"] == rng and rv["content"]:
                entry["reviews"].append(rv)
        chapters_entries[key]["entries"].append(entry)

    covered_ranges = {m.get("range", "") for m in marks_list}
    for rv in reviews:
        if not rv["content"]:
            continue
        attached = False
        for key in chapter_order:
            for e in chapters_entries[key]["entries"]:
                if e["kind"] == "mark" and any(x["range"] == rv["range"] for x in e["reviews"]):
                    attached = True
                    break
            if attached:
                break
        if attached:
            continue
        if rv["range"] in covered_ranges:
            continue
        uid = rv.get("chapterUid", "")
        cname = rv.get("chapterName") or chapters_map.get(uid, "") or chapter_order_map.get(str(uid), {}).get("title", "") or chapter_fallback
        key = get_or_create_chapter(uid, cname)
        chapters_entries[key]["entries"].append({"kind": "review", "review": rv})

    def chapter_sort_key(key):
        uid = key if not key.startswith("rv-") else ""
        if uid in chapter_order_map:
            return chapter_order_map[uid]["idx"]
        return 99999
    chapter_order.sort(key=chapter_sort_key)

    for key in chapter_order:
        chapters_entries[key]["entries"].sort(key=lambda e: range_start(e["mark"]["range"]) if e["kind"] == "mark" else range_start(e["review"].get("range", "")))

    core_view = CORE_VIEWS.get(book_id, "")

    lines = []
    lines.append(f"# 📖 《{title}》读书笔记")
    lines.append("")
    if intro:
        lines.append(f"> 📝 **简介**：{intro}")
        lines.append("")

    lines.append("## 📋 书籍信息")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 📕 书名 | 《{title}》 |")
    if author:
        lines.append(f"| ✍️ 作者 | {author} |")
    if translator:
        lines.append(f"| 🖋️ 译者 | {translator} |")
    if category:
        lines.append(f"| 🏷️ 分类 | {category} |")
    if publisher:
        lines.append(f"| 🏢 出版社 | {publisher} |")
    if publish_time:
        lines.append(f"| 📅 出版时间 | {publish_time[:10]} |")
    if isbn:
        lines.append(f"| 🔖 ISBN | {isbn} |")
    if deep_link:
        lines.append(f"| 🔗 阅读 | [打开阅读]({deep_link}) |")
    lines.append("")

    lines.append("## 🎯 读书前 · 阅读计划")
    lines.append("")
    lines.append("> ✍️ 阅读前填写，带着目标去读")
    lines.append("")
    lines.append("- **阅读目的**：（为什么读这本书？想解决什么问题？）")
    lines.append("- **预设问题**：（带着哪 2-3 个问题去读？）")
    lines.append("- **记录方式**：微信读书划线 + 想法，同步整理至 ima")
    lines.append("")

    lines.append("## 📖 读书时 · 划线摘录")
    lines.append("")
    lines.append(f"> 📌 划线共 {len(marks_list)} 条 · 💭 想法 {len(reviews)} 条 · 点击划线可在微信读书 App 中查看")
    lines.append("")

    for key in chapter_order:
        ch = chapters_entries[key]
        lines.append(f"### 📄 {ch['name']}")
        lines.append("")
        for e in ch["entries"]:
            if e["kind"] == "mark":
                m = e["mark"]
                text = m.get("markText", "")
                if deep_link:
                    linked = f"[{text}]({deep_link})"
                else:
                    linked = f"**{text}**"
                lines.append(f"> 📌 {linked}")
                for rv in e["reviews"]:
                    lines.append(">")
                    add_review_lines(lines, rv["content"])
                lines.append(">")
                lines.append(f"> ⏱ {ts2date(m.get('createTime',0))}")
                lines.append("")
            else:
                rv = e["review"]
                if rv.get("abstract"):
                    abstract = rv["abstract"]
                    if deep_link:
                        linked = f"[{abstract}]({deep_link})"
                    else:
                        linked = f"**{abstract}**"
                    lines.append(f"> 📌 {linked}")
                    lines.append(">")
                    add_review_lines(lines, rv["content"])
                    lines.append(">")
                    lines.append(f"> ⏱ {ts2date(rv.get('createTime',0))}")
                    lines.append("")
                else:
                    add_review_lines(lines, rv["content"])
                    lines.append(">")
                    lines.append(f"> ⏱ {ts2date(rv.get('createTime',0))}")
                    lines.append("")

    lines.append("## 🧠 读书后 · 思考沉淀")
    lines.append("")
    if core_view:
        lines.append("**💡 核心观点**（基于你的划线提炼）：")
        lines.append("")
        lines.append(f"> {core_view}")
        lines.append("")
    lines.append("**✍️ 我的解读**：（读完后用自己的话复述，检验是否真正理解）")
    lines.append("")
    lines.append("**✅ 行动清单**：（书中的方法如何应用到工作/生活？列出 1-3 条可执行行动）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本笔记由微信读书划线自动整理 · 格式：读书前计划 → 读书时摘录 → 读书后沉淀*")

    return "\n".join(lines)

def main():
    """遍历 config.json 里配置的书籍，生成笔记"""
    for b in CFG["weread"]["books"]:
        abbr = b["abbr"]
        disp = b.get("title", abbr)
        mf = f"weread_{abbr}_marks.json"
        rf = f"weread_{abbr}_reviews.json"
        inf = f"weread_{abbr}_info.json"
        cf = f"weread_{abbr}_chapters.json"
        out_name = b.get("md_file") or f"note_{abbr}.md"
        out = os.path.join(WORKDIR, out_name)
        try:
            md = build_note(mf, rf, inf, cf, disp)
        except FileNotFoundError as e:
            print(f"[跳过] {abbr}: 缺少数据文件（请先运行 fetch_weread.py）")
            continue
        with open(out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"written: {out} ({len(md)} chars)")

if __name__ == "__main__":
    main()
