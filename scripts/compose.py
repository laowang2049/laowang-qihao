#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compose.py — 把生图模型的产出收拾成能直接发的成品。

两种模式：
  keep    模型把文字也一并画对了 → 只做规范化：去水印、裁到目标比例
  retext  模型把字画错了 → 只取它的插画区，把 typeset 排好的字重新贴回去

用法：
  python scripts/compose.py --model out.png --draft draft.json --out final.jpg
  python scripts/compose.py --model out.png --draft draft.json --out final.jpg --mode retext
  python scripts/compose.py --model out.png --size 1080x1440 --out final.jpg   # 没底稿时

--trim-bottom 0.035 是默认去水印比例（模型常在右下角压一行水印）。
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def cover(img, w, h, anchor="center"):
    """等比放大到铺满 (w,h) 再裁切。anchor: center / top（保上边）/ bottom（保下边）。"""
    r = max(w / img.width, h / img.height)
    nw, nh = max(1, round(img.width * r)), max(1, round(img.height * r))
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = {"center": (nh - h) // 2, "top": 0, "bottom": max(0, nh - h)}[anchor]
    return img.crop((left, top, left + w, top + h))


def trim_watermark(img, frac):
    """裁掉底部一段再去掉拉伸回原尺寸——比直接裁掉更不容易看出画幅变了。"""
    if frac <= 0:
        return img
    w, h = img.size
    keep = int(h * (1 - frac))
    return img.crop((0, 0, w, keep)).resize((w, h), Image.LANCZOS)


def load_draft(path):
    p = Path(path)
    if not p.exists():
        sys.exit(f"找不到排版文件：{p}（先跑 typeset.py --json-out）")
    return json.loads(p.read_text(encoding="utf-8"))


def mode_keep(model, draft, out, trim):
    w, h = draft["size"] if draft else (model.width, model.height)
    img = trim_watermark(model, trim)
    # 锚顶部：文字在上面，宁可裁掉插画底部，也不能切到文字
    cover(img, w, h, anchor="top").save(out, quality=95)
    return w, h


def blend_seam(canvas, y, paper, height=80):
    """把插画顶边往纸色里融一段，避免文字区和插画之间出现一条硬线。"""
    if y <= 0 or height <= 0:
        return
    w = canvas.width
    grad = Image.new("L", (1, height))
    for i in range(height):
        grad.putpixel((0, i), int(255 * (1 - i / height)))
    canvas.paste(Image.new("RGB", (w, height), paper), (0, y), grad.resize((w, height)))


def mode_retext(model, draft, out, trim):
    w, h = draft["size"]
    text_h = draft["text_h"]
    paper = tuple(draft.get("paper") or (255, 254, 252))
    ink = tuple(draft.get("ink") or (38, 34, 30))

    # 模型图里文字区占的比例，和底稿一致；往下就是它的插画
    top = int(model.height * (text_h / h))
    # 水印按整图高度算，不能按插画区算（否则裁不够）
    bottom = model.height - int(model.height * trim)
    ill = model.crop((0, top, model.width, max(top + 1, bottom)))

    canvas = Image.new("RGB", (w, h), paper)
    canvas.paste(cover(ill, w, h - int(text_h)), (0, int(text_h)))
    blend_seam(canvas, int(text_h), paper)

    # 把排版信息原样重画一遍，保证和底稿一模一样
    font = ImageFont.truetype(draft["font_path"], draft["font_size"])
    d = ImageDraw.Draw(canvas)
    lh = draft["line_height"]
    block = len(draft["wrapped"]) * lh
    y = (text_h - block) / 2
    for line in draft["wrapped"]:
        x = draft["margin_x"]
        if not x:
            x = (w - font.getlength(line)) / 2
        d.text((x, y), line, font=font, fill=ink)
        y += lh

    canvas.save(out, quality=95)
    return w, h


def main():
    ap = argparse.ArgumentParser(description="成品合成")
    ap.add_argument("--model", required=True, help="生图模型输出的图")
    ap.add_argument("--draft", help="typeset.py 产出的 draft.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="keep", choices=["keep", "retext"])
    ap.add_argument("--size", help="没有 draft 时用，形如 1080x1440")
    ap.add_argument("--trim-bottom", type=float, default=0.035, help="底部去水印比例，默认 3.5%%")
    args = ap.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    model = Image.open(args.model).convert("RGB")
    draft = load_draft(args.draft) if args.draft else None

    if draft is None:
        if not args.size:
            sys.exit("没有 --draft 就必须给 --size，例如 --size 1080x1440")
        w, h = (int(v) for v in args.size.lower().split("x"))
        draft = {"size": [w, h]}
        if args.mode == "retext":
            sys.exit("retext 模式需要 --draft（要知道文字区高度和排版）")

    if args.mode == "retext":
        w, h = mode_retext(model, draft, args.out, args.trim_bottom)
    else:
        w, h = mode_keep(model, draft, args.out, args.trim_bottom)

    print(f"已合成 {args.out}（{w}×{h}，模式 {args.mode}，去水印 {args.trim_bottom:.1%}）")


if __name__ == "__main__":
    main()
