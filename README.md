# 微信读书 → ima 知识库 · 自动化流水线

把"读过就忘"的划线，变成**结构化、可检索、会生长**的个人知识库。

不用第三方依赖，纯 Python 标准库，跑在你自己电脑上，数据不经过任何中间服务器。

---

## 解决什么问题

读书时我们做了大量划线、写了大量想法 —— 但它们锁在微信读书里：

- 搜不到、关联不起来
- 换设备就散
- 读完就忘，划线变成"数字坟场"
- 手动整理一次要几小时，坚持不下来

这个项目做的事：**把微信读书的划线 + 想法自动同步到 ima.copilot 笔记/知识库，并按固定模板结构化**，让每本书的笔记长得一样、能被检索、能和别的知识连起来。

---

## 实际效果（真实数据）

| 指标 | 数值 |
|---|---|
| 已同步书籍 | 8 本 |
| 累计划线 | 978 条 |
| 累计想法 | 327 条 |
| 单次同步耗时 | 几分钟（手动整理约数小时） |

---

## 它是怎么工作的

```
微信读书 API
      │  ① 拉取：书架 / 划线 / 想法
      ▼
  fetch_weread.py
      │  ② 排序整序：章节顺序 + 划线位置（不用接口返回的乱序）
      ▼
   gen_notes.py
      │  ③ 套模板：书籍信息 → 阅读计划 → 划线摘录 → 思考沉淀
      ▼
  note_<书名>.md
      │  ④ 上传 + 建笔记 + 归档
      ▼
  update_notes.py  ──▶  ima 知识库
      │  ⑤ 增量更新：只处理有变化的书（对比 sort 字段）
      ▼
  ✅ 知识库自动生长
```

---

## 快速开始

### 0. 环境要求

- Python 3.8+
- 无第三方依赖（不需要 pip install）
- 可访问微信读书 API 与 ima openapi 的网络

### 1. 拿到项目

```bash
git clone https://github.com/你的GitHub用户名/weread-to-ima.git
```

### 2. 填配置

```bash
cp config.example.json config.json
```

打开 `config.json`，把占位符换成你自己的：

- `ima.kb_id` / `ima.kb_folder_id`：目标知识库 ID 与文件夹 ID
- `ima.notebook_folder_id`：笔记所在笔记本
- `notes[].note_id`：已有笔记的 ID（首次运行可留空，由脚本创建后再回填）
- `weread.books[]`：要同步的书（`book_id` 可在微信读书网页版书籍详情页 URL 里找到）

### 3. 设置凭证（只走环境变量）

```bash
export WEREAD_API_KEY="你的微信读书 API Key"
export IMA_OPENAPI_CLIENTID="你的 ima clientid"
export IMA_OPENAPI_APIKEY="你的 ima apikey"
```

> ⚠️ 凭证永远不要写进 `config.json`，也不要提交到仓库。`.gitignore` 已默认排除 `config.json` 与 `data/`。

### 4. 跑

```bash
# 拉取全部书（或指定缩写：python3 scripts/fetch_weread.py fq nwe）
python3 scripts/fetch_weread.py

# 生成笔记 markdown
python3 scripts/gen_notes.py

# 同步到 ima（自动检测变化，只更新有改动的书）
python3 scripts/update_notes.py
```

---

## 目录结构

```
.
├── config.example.json   # 配置模板（复制为 config.json）
├── config_loader.py      # 统一配置加载 + 环境变量校验
├── core_views.json       # 每本书的「核心观点」摘要（可选，留空即用模板占位）
├── scripts/
│   ├── fetch_weread.py   # 拉取划线 / 想法 / 目录 / 书籍信息
│   ├── gen_notes.py      # 按固定模板生成笔记 markdown
│   └── update_notes.py   # 增量写入 ima 笔记
├── templates/
│   └── NOTE_TEMPLATE.md  # 笔记模板
└── docs/
    ├── 01-踩坑记录.md
    ├── 02-配置说明.md
    └── 03-复盘文章-初稿.md
```

---

## 核心设计（也是踩过的坑）

| 问题 | 解法 |
|---|---|
| 接口返回乱序 | 强制按 `chapterIdx` 升序 + 划线 `range` 位置升序重排 |
| 想法被截断 | `count` 必须传 100（默认会丢旧想法） |
| 同一划线多条想法 | 禁止按 `range` 去重（会吞掉第二条） |
| 每次全量跑太慢 | 用书架 `sort` 字段做变化检测，只更新有变动的书 |
| 重复导入不可逆 | 入库前必须先查目标文件夹，检查同名条目 |
| 笔记格式漂移 | 固定模板 + 增量更新只删自动生成块，保留手写内容 |

更细的踩坑过程见 [`docs/01-踩坑记录.md`](docs/01-踩坑记录.md)。

---

## 常见问题

**Q：我的笔记会被上传到别的地方吗？**
不会。脚本只做两件事：调用微信读书接口取你自己的数据，调用 ima openapi 写进你自己的知识库。没有中间服务器，没有数据收集。

**Q：微信读书 API Key 怎么获取？**
本项目基于微信读书开放给 AI Agent 的 gateway 接口，Key 需要你自己申请/获取（各平台方式不同，且可能变化）。项目只负责调用，不提供 Key。

**Q：能同步公众号文章吗？**
可以。在 `config.json` 的书籍项里加 `"type": "article"`，`book_id` 用 `MP_WXS_` 开头的 ID。

**Q：会覆盖我手动写的笔记内容吗？**
不会。增量更新只删除模板自动生成的部分，手写内容和图片会保留。

---

## Roadmap

- [ ] 支持导出为 Obsidian / Logseq 格式
- [ ] 支持按标签自动分组
- [ ] 提供 GitHub Actions 定时同步示例
- [ ] 英文文档

---

## 贡献

欢迎提 Issue 和 PR。如果你踩到新的坑，尤其欢迎补进 `docs/01-踩坑记录.md` —— 这个项目一半的价值在"记录了什么不管用"。

---

## License

MIT
