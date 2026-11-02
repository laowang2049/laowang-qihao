#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""picker.py — 生成 341 画风选型页（纯静态 html，双击就能开，不起服务）。

用法：
    python scripts/picker.py             # 生成并打开 library/picker.html
    python scripts/picker.py --no-open   # 只生成，打印路径（CI / 无桌面环境用）
    python scripts/picker.py --path      # 只打印路径，给 AI 拿去交给用户

选型流程：
    用户在页面里点「就选这个画风」→ 编号自动进剪贴板 → 回对话窗口 Ctrl+V 粘给 AI。
    页面不写文件、不连本地端口，所以没有任何服务要启、要停、要等。

为什么不写文件了：起 http 服务只为把选择写回磁盘，代价是一个常驻进程 + 端口占用 +
用户看不见的后台窗口。剪贴板一样能传递一个 6 字符的编号，而且断了服务也不影响。
"""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
INDEX = LIB / "index.json"
TPL = ROOT / "engine" / "picker.tpl.html"
OUT = LIB / "picker.html"
CHOICE = ROOT / "picks" / "choice.json"

FIELDS = ("id", "name", "cat", "cat_label", "look", "fit",
          "quality", "prompt_chars", "keywords", "still")

# 打开页面就落在这个分类上（98 条奥斯卡风格全部带预留图，适合当默认门面）。
# 想改成「全部」就把这里设为 None。
DEFAULT_CAT = "O_奥斯卡98部"


def load_index():
    if not INDEX.exists():
        sys.exit("索引不存在：先跑 python scripts/style.py build")
    return json.loads(INDEX.read_text(encoding="utf-8"))


def build_page():
    idx = load_index()
    entries = [e for e in idx["entries"] if not e.get("broken")]

    cats = {}
    for e in entries:
        c = cats.setdefault(e["cat"], {"cat": e["cat"], "label": e["cat_label"], "n": 0})
        c["n"] += 1

    current = None
    if CHOICE.exists():
        try:
            current = json.loads(CHOICE.read_text(encoding="utf-8")).get("id")
        except Exception:
            current = None

    default_cat = DEFAULT_CAT if DEFAULT_CAT in cats else None
    if DEFAULT_CAT and not default_cat:
        print(f"注意：默认分类 {DEFAULT_CAT} 在索引里不存在，页面仍从「全部」开始。")

    data = {
        "count": idx["count"],
        "shown": len(entries),
        "with_still": sum(1 for e in entries if e["still"]),
        "no_prompt": sum(1 for e in entries if e["quality"] == "empty"),
        "current": current,
        "default_cat": default_cat,
        "cats": sorted(cats.values(), key=lambda c: -c["n"]),
        # still 是相对 library/ 的路径，picker.html 就在 library/ 里，直接当相对 URL 用
        "entries": [{k: e.get(k) for k in FIELDS} for e in entries],
    }
    tpl = TPL.read_text(encoding="utf-8")
    OUT.write_text(tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
                   encoding="utf-8")
    return OUT, data


def main():
    ap = argparse.ArgumentParser(description="341 画风选型页（静态 html）")
    ap.add_argument("--no-open", action="store_true", help="只生成，不打开浏览器")
    ap.add_argument("--path", action="store_true", help="只打印文件路径")
    args = ap.parse_args()

    page, data = build_page()

    if args.path:
        print(page)
        return

    print(f"选型页已生成：{page}")
    print(f'共 {data["count"]} 条，页面里显示 {data["shown"]} 条 · '
          f'有预留画风图 {data["with_still"]} 条 · 提示词缺失 {data["no_prompt"]} 条（默认折叠）')
    print("用户点「就选这个画风」→ 编号自动复制 → 回对话粘贴即可。")

    if not args.no_open:
        try:
            webbrowser.open(page.as_uri())
            print("已在浏览器打开。")
        except Exception as e:
            print(f"自动打开失败（{e}），直接双击这个文件也行。")


if __name__ == "__main__":
    main()
