#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonts.py — 找一个能写中文的字体。

优先级（从高到低）：
  1. 技能自带的 fonts/ 目录：用户往这里丢 .ttf/.otf/.ttc 就优先用它
     （推荐霞鹜文楷 LXGW WenKai，OFL 协议，手写楷体观感最接近参考图）
  2. 系统楷体：Windows simkai.ttf / macOS Kaiti / Linux Noto Serif CJK
  3. 系统其它中文字体（黑体、宋体）兜底

标题（type1）要粗黑体，正文（type2）要楷体，这两个用途分开取。
"""

from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent
USER_FONT_DIR = ROOT / "fonts"

KAI = [
    ("C:/Windows/Fonts/simkai.ttf", "系统楷体"),
    ("/System/Library/Fonts/Supplemental/Kaiti.ttc", "系统楷体"),
    ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", "Noto Serif CJK"),
    ("/usr/share/fonts/truetype/arphic/uming.ttc", "AR PL UMing"),
    ("C:/Windows/Fonts/msyh.ttc", "微软雅黑"),
    ("/System/Library/Fonts/PingFang.ttc", "苹方"),
]

HEI = [
    ("C:/Windows/Fonts/simhei.ttf", "系统黑体"),
    ("C:/Windows/Fonts/msyhbd.ttc", "微软雅黑 Bold"),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", "宋体"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "Noto Sans CJK Bold"),
    ("C:/Windows/Fonts/msyh.ttc", "微软雅黑"),
]


def _user_fonts():
    """fonts/ 下用户自己放的字体，文件名里带 bold/hei/黑 的当标题字体。"""
    if not USER_FONT_DIR.is_dir():
        return [], []
    files = sorted(p for p in USER_FONT_DIR.iterdir()
                   if p.suffix.lower() in (".ttf", ".otf", ".ttc"))
    bold = [p for p in files if any(k in p.name.lower() for k in ("bold", "hei", "黑", "heavy", "black"))]
    return files, bold


def _has_cjk(font):
    try:
        return font.getmask("中").getbbox() is not None
    except Exception:
        return False


def _try(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        f = ImageFont.truetype(str(p), 32)
    except Exception:
        return None
    return (p, f) if _has_cjk(f) else None


def pick_font(kind="kai", size=32):
    """返回 (ImageFont, 字体路径, 人类可读的名字)。找不到就抛异常。"""
    users, user_bold = _user_fonts()
    ordered = list(users if kind == "kai" else (user_bold or users)) + \
              [(Path(p), n) for p, n in (KAI if kind == "kai" else HEI)]
    for path, label in ordered:
        hit = _try(path)
        if hit:
            f = ImageFont.truetype(str(hit[0]), size)
            return f, hit[0], str(label)
    raise SystemExit(
        "找不到可用的中文字体。\n"
        "解决：把一个中文 .ttf 放进 " + str(USER_FONT_DIR) + "\n"
        "推荐霞鹜文楷（OFL，可商用）：https://github.com/lxgw/LxgwWenKai/releases"
    )


if __name__ == "__main__":
    for k in ("kai", "hei"):
        f, p, n = pick_font(k, 40)
        print(f"{k}: {p}（{n}）")
