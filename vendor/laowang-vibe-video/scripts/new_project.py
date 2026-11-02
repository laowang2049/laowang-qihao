#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_project.py — 建一个项目骨架。

    python scripts/new_project.py --theme "谣言为什么跑得快" --style L36 --slug rumor
    python scripts/new_project.py --theme "…" --style O10 --slug demo --duration 20

会读 picked 画风的元信息写进 brief.json，并把主题、时长、画幅、第一句文案填进 index.html。
之后要改的就是 projects/<slug>/index.html 一个文件。

--size 三种写法都认：9:16 / 16:9（简写）、1080x1920（像素）、1:1 等常见比例
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "library" / "index.json"
TPL = ROOT / "engine" / "template.html"
RUNTIME = ROOT / "engine" / "runtime.js"

# 常见画幅：短边 1080 起，长边按比例算
PRESETS = {
    "16:9": (1920, 1080),   # 横版：B 站 / YouTube / 公众号
    "9:16": (1080, 1920),   # 竖版：抖音 / 视频号 / Reels
    "4:3": (1440, 1080),
    "3:4": (1080, 1440),
    "1:1": (1080, 1080),
}


def parse_size(s):
    """'9:16' / '16:9' / '1080x1920' / '1080*1920' 都能解析成 (宽, 高)。"""
    t = str(s).strip().lower().replace("：", ":").replace("×", "x").replace("*", "x")
    if t in PRESETS:
        return PRESETS[t]
    if "x" in t:
        a, b = t.split("x", 1)
        try:
            w, h = int(a), int(b)
        except ValueError:
            sys.exit(f"--size 看不懂：{s}。写 9:16 / 16:9，或 1080x1920")
        if w < 2 or h < 2:
            sys.exit(f"--size 太小：{s}")
        return w, h
    sys.exit(f"--size 看不懂：{s}。写 9:16 / 16:9，或 1080x1920")


def load_style(sid):
    if not INDEX.exists():
        sys.exit("索引不存在：先跑 python scripts/style.py build")
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    e = next((x for x in idx["entries"] if x["id"].upper() == sid.upper()), None)
    if not e:
        sys.exit(f"库里没有 {sid}。用 python scripts/style.py search 找编号。")
    return e


def main():
    ap = argparse.ArgumentParser(description="建项目")
    ap.add_argument("--theme", required=True)
    ap.add_argument("--style", required=True, help="画风编号，例如 L36")
    ap.add_argument("--slug", default=None, help="目录名，英文/拼音，默认 auto")
    ap.add_argument("--duration", type=float, default=30, help="秒；按用户确认的时长填")
    ap.add_argument("--size", default="16:9", help="9:16 / 16:9 / 1080x1920")
    ap.add_argument("--copy", default=None, help="文案文件（每行一句）；不给就用占位")
    args = ap.parse_args()

    if args.duration <= 0:
        sys.exit("--duration 要大于 0")

    slug = args.slug or ("v" + datetime.now().strftime("%m%d%H%M"))
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", slug):
        sys.exit("--slug 只能用英文、数字、下划线、连字符")

    e = load_style(args.style)
    w, h = parse_size(args.size)
    proj = ROOT / "projects" / slug
    if proj.exists():
        sys.exit(f"{proj} 已存在。换个 --slug，或先删掉它。")
    proj.mkdir(parents=True)

    lines = []
    if args.copy:
        cp = Path(args.copy)
        if not cp.exists():
            sys.exit(f"文案文件不存在：{cp}")
        lines = [x.strip() for x in cp.read_text(encoding="utf-8").splitlines() if x.strip()]
    first = lines[0] if lines else "把主题换成你要讲的那句话"

    brief = {
        "slug": slug,
        "theme": args.theme,
        "width": w,
        "height": h,
        "duration": args.duration,
        "style": {
            "id": e["id"],
            "name": e["name"],
            "cat": e["cat_label"],
            "md": "library/" + e["md"],
            "sha256": e["sha256"],
            "prompt_chars": e["prompt_chars"],
        },
        "copy": lines,
        # 音轨由 scripts/audio.py 落成 projects/<slug>/audio/track.wav 后回填这一栏
        # mode: default（内置 vibe 增智小曲）/ file（用户上传）/ tts（系统自动配音）
        "audio": {"mode": "unset"},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (proj / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8")

    html = TPL.read_text(encoding="utf-8")
    html = html.replace("size: [1920, 1080],", "size: [%d, %d]," % (w, h))
    html = html.replace("title: '标题占位',", "title: " + json.dumps(args.theme, ensure_ascii=False) + ",")
    html = html.replace("duration: 6,", "duration: %g," % args.duration)
    html = html.replace("{ text: '把主题换成你要讲的那句话', at: 0.55 },",
                        "{ text: " + json.dumps(first, ensure_ascii=False) + ", at: 0.55 },")
    # 把 brief 塞进去，画代码时可以随时读
    html = html.replace("const SCENE = {",
                        "const BRIEF = " + json.dumps(brief, ensure_ascii=False, indent=1) + ";\n\nconst SCENE = {")
    if "size: [%d, %d]," % (w, h) not in html:
        sys.exit("模板里没找到 size 占位，engine/template.html 被改坏了，先修模板")
    (proj / "index.html").write_text(html, encoding="utf-8")

    shutil.copy2(RUNTIME, proj / "runtime.js")

    orient = "竖版" if h > w else ("横版" if w > h else "方形")
    print(f"项目已建：{proj}")
    print(f"  画风：{e['id']} {e['name']}（{e['cat_label']}，提示词 {e['prompt_chars']} 字符）")
    print(f"  规格：{w}×{h}（{orient}）  {args.duration:g}s")
    print(f"  要改的文件：{(proj / 'index.html').relative_to(ROOT)}")
    print()
    print("下一步：")
    print(f"  python scripts/render.py projects/{slug} --still 2 6")


if __name__ == "__main__":
    main()
