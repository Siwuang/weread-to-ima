#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_loader.py —— 统一配置加载器

把原先硬编码在脚本里的个人配置（书 ID、路径、笔记 ID、知识库 ID）
统一抽到 config.json，让脚本变成"填配置即可用"。

用法：
    from config_loader import load_config, require_env
    cfg = load_config()
    for b in cfg["weread"]["books"]:
        print(b["abbr"], b["book_id"])
"""
import json
import os
import sys

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
EXAMPLE_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.example.json")


def load_config(path=None):
    """加载配置。找不到 config.json 时，提示从 example 复制。"""
    path = path or DEFAULT_CONFIG
    if not os.path.exists(path):
        print(f"[!] 未找到配置文件: {path}")
        print(f"[!] 请先复制示例：cp {EXAMPLE_CONFIG} {DEFAULT_CONFIG}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)

    # workdir 相对路径 → 转为绝对路径
    wd = cfg.get("workdir", "./data")
    if not os.path.isabs(wd):
        wd = os.path.abspath(os.path.join(os.path.dirname(path), wd))
    cfg["workdir"] = wd
    os.makedirs(wd, exist_ok=True)
    return cfg


def require_env(name):
    """读取必需的环境变量，不存在时给出明确提示。"""
    v = os.environ.get(name)
    if not v:
        print(f"[!] 缺少环境变量: {name}")
        print(f"[!] 请先设置： export {name}=\"你的值\"")
        sys.exit(1)
    return v


def book_by_abbr(cfg, abbr):
    for b in cfg["weread"]["books"]:
        if b["abbr"] == abbr:
            return b
    return None


if __name__ == "__main__":
    cfg = load_config()
    print("workdir:", cfg["workdir"])
    print("书籍数:", len(cfg["weread"]["books"]))
    for b in cfg["weread"]["books"]:
        print(f"  {b['abbr']:8s} {b['book_id']:20s} {b['title']}")
