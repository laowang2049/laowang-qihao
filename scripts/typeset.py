#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""typeset.py — 把文案排成一张「底稿」：文字在上，下方留白给生图模型作画。

规则（和 SKILL.md 一致，改这里就要同步改文档）：
  · 文字总高度不超过画幅 60%（标题型不超过 25%）
  · 字号 60→32 自适应，放不下就报 overflow，不硬塞
  · 断行优先落在标点处，避头尾，禁孤字
  · 行距 1.75 倍字号，左右边距 8.5%
  · 200 字是舒适线：>200 提醒，>260 强烈建议截断

用法：
  python scripts/typeset.py --text "文案" --ratio 3:4 --out draft.jpg
  python scripts/typeset.py --text "一句话提问" --ratio 16:9 --kind title --out draft.jpg
  python scripts/typeset.py --text "文案" --ratio 3:4 --analyze --json   # 只算不画
"""

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from fonts import pick_font

ROOT = Path(__file__).resolve().parent.parent
PAPER = (255, 254, 252)
INK = (38, 34, 30)

SIZES = {"16:9": (1920, 1080), "3:4": (1080, 1440), "9:16": (1080, 1920)}
MARGIN_X = 0.085
LINE_HEIGHT = 1.75
COPY_CAP = 0.60
TITLE_CAP = 0.25

NO_LINE_START = "，。！？；：、）」』】〉》”’"
NO_LINE_END = "「『（【〈《“‘"
BREAKABLE = "，、；："

COMFORT_CHARS = 200      # 舒适线
MAX_CHARS = 260          # 超过就建议截断
TITLE_MAX_CHARS = 28


def split_sentences(text):
    return [s for s in re.split(r"(?<=[。！？；!?;])", text.strip()) if s]


def wrap_copy(text, font, max_w):
    """按句排，溢出时回退到最近的标点断行；避头尾、禁孤字。"""
    lines, cur = [], ""
    for sent in split_sentences(text):
        # 上一行只剩一两个字的空间时不硬塞新句子
        if cur and max_w - font.getlength(cur) < min(len(sent), 3) * font.size:
            lines.append(cur)
            cur = ""
        for ch in sent:
            if font.getlength(cur + ch) <= max_w:
                cur += ch
                continue
            cut = -1
            # 回退窗口：只在最近 10 个字里找标点断行，太远会把行拉得很短
            for i in range(len(cur) - 1, max(len(cur) - 10, 1), -1):
                if cur[i] in BREAKABLE:
                    cut = i
                    break
            if cut > 0:
                lines.append(cur[:cut + 1])
                cur = cur[cut + 1:] + ch
            elif ch in NO_LINE_START and len(cur) > 1:
                lines.append(cur[:-1])
                cur = cur[-1] + ch
            elif cur and cur[-1] in NO_LINE_END and len(cur) > 1:
                lines.append(cur[:-1])
                cur = cur[-1] + ch
            else:
                lines.append(cur)
                cur = ch
    if cur:
        lines.append(cur)
    # 末行只剩 1~2 个字：从上一行借
    if len(lines) >= 2 and len(lines[-1]) <= 2 and len(lines[-2]) > 4:
        n = 3 - len(lines[-1])
        lines[-1] = lines[-2][-n:] + lines[-1]
        lines[-2] = lines[-2][:-n]
    return lines


def layout_copy(text, w, h):
    max_w = w * (1 - 2 * MARGIN_X)
    for fs in (60, 56, 52, 48, 44, 40, 36, 34, 32):
        font, path, name = pick_font("kai", fs)
        lines = wrap_copy(text, font, max_w)
        lh = fs * LINE_HEIGHT
        text_h = len(lines) * lh + fs * 2.6
        if text_h <= h * COPY_CAP:
            return {"font": font, "font_path": str(path), "font_name": name, "font_size": fs,
                    "lines": lines, "line_height": lh, "text_h": text_h,
                    "margin_x": w * MARGIN_X, "max_w": max_w}
    return None


def layout_title(text, w, h):
    """标题型：一行放得下就一行，放不下拆两行；总高不超过画幅 25%。"""
    max_w = w * 0.92
    for fs in (96, 88, 80, 72, 64, 56):
        font, path, name = pick_font("hei", fs)
        if font.getlength(text) <= max_w:
            return {"font": font, "font_path": str(path), "font_name": name, "font_size": fs,
                    "lines": [text], "line_height": fs * 1.18, "text_h": fs * 2.4,
                    "margin_x": (w - font.getlength(text)) / 2, "max_w": max_w}
    # 两行
    half = (len(text) + 1) // 2
    for fs in (72, 64, 56, 48, 44):
        font, path, name = pick_font("hei", fs)
        l1, l2 = text[:half], text[half:]
        if font.getlength(l1) <= max_w and font.getlength(l2) <= max_w:
            lh = fs * 1.35
            text_h = lh * 2 + fs * 1.2
            if text_h <= h * TITLE_CAP:
                return {"font": font, "font_path": str(path), "font_name": name, "font_size": fs,
                        "lines": [l1, l2], "line_height": lh, "text_h": text_h,
                        "margin_x": None, "max_w": max_w}
    return None


def draw_text(canvas, lay, kind):
    d = ImageDraw.Draw(canvas)
    w, h = canvas.size
    lh = lay["line_height"]
    block = len(lay["lines"]) * lh
    y = (lay["text_h"] - block) / 2 if lay["text_h"] else 0
    if kind == "title":
        y = max(0, (lay["text_h"] - block) / 2)
    for line in lay["lines"]:
        x = lay["margin_x"]
        if x is None:
            x = (w - lay["font"].getlength(line)) / 2
        d.text((x, y), line, font=lay["font"], fill=INK)
        y += lh


def classify(text):
    n = len(text)
    if n <= COMFORT_CHARS:
        return "ok"
    if n <= MAX_CHARS:
        return "warn"
    return "long"


def main():
    ap = argparse.ArgumentParser(description="排版底稿")
    ap.add_argument("--text", required=True)
    ap.add_argument("--ratio", default="3:4", choices=list(SIZES))
    ap.add_argument("--kind", default="copy", choices=["copy", "title"])
    ap.add_argument("--out", help="输出底稿路径（.jpg/.png）")
    ap.add_argument("--json-out", help="同时把排版信息写成 json，compose 要用")
    ap.add_argument("--analyze", action="store_true", help="只计算，不画图")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = ap.parse_args()

    text = args.text.strip()
    w, h = SIZES[args.ratio]
    lay = layout_title(text, w, h) if args.kind == "title" else layout_copy(text, w, h)
    level = classify(text) if args.kind == "copy" else (
        "ok" if len(text) <= TITLE_MAX_CHARS else "long")

    if lay is None:
        out = {"ok": False, "reason": "overflow", "kind": args.kind, "chars": len(text),
               "level": "long", "ratio": args.ratio, "size": [w, h]}
        print(json.dumps(out, ensure_ascii=False, indent=1) if args.json
              else f"排不下：{len(text)} 字，最小字号仍然超过画幅上限。建议截到 {COMFORT_CHARS} 字内。")
        sys.exit(3)

    ratio_used = lay["text_h"] / h
    info = {
        "ok": True, "kind": args.kind, "ratio": args.ratio, "size": [w, h],
        "chars": len(text), "level": level,
        "font_size": lay["font_size"], "font_name": lay["font_name"],
        "font_path": lay["font_path"], "lines": len(lay["lines"]),
        "line_height": round(lay["line_height"], 1),
        "text_h": round(lay["text_h"], 1), "text_ratio": round(ratio_used, 3),
        "margin_x": round(lay["margin_x"] or 0, 1),
        "wrapped": lay["lines"], "paper": list(PAPER), "ink": list(INK),
    }

    if not args.analyze:
        if not args.out:
            sys.exit("要么给 --out 出图，要么加 --analyze 只算")
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGB", (w, h), PAPER)
        draw_text(canvas, lay, args.kind)
        canvas.save(args.out, quality=95)
        info["out"] = args.out
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
            info["json_out"] = args.json_out

    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=1))
    else:
        tip = {"ok": "", "warn": f" · 超过 {COMFORT_CHARS} 字舒适线，画面会偏密",
               "long": f" · 太长，建议截到 {COMFORT_CHARS} 字内"}[level]
        print(f'{len(text)} 字 · {lay["font_size"]}px · {len(lay["lines"])} 行 · '
              f'文字区占画幅 {ratio_used:.0%}{tip}')
        print(f'字体：{lay["font_name"]}')


if __name__ == "__main__":
    main()
