#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doctor.py — 开工前自检。

    python scripts/doctor.py

ready 为 true 才能做第 1、2 种；第 3 种另外需要 playwright + ffmpeg，
这一项不影响 ready，只在需要时提醒。
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CORE = [
    "SKILL.md",
    "scripts/typeset.py",
    "scripts/compose.py",
    "scripts/fonts.py",
    "assets/type1-example.jpg",
    "assets/type2-example.jpg",
    "assets/copy-prompt.md",
    "vendor/laowang-vibe-video/SKILL.md",
    "vendor/laowang-vibe-video/scripts/render.py",
    "vendor/laowang-vibe-video/scripts/audio.py",
    "vendor/laowang-vibe-video/assets/bgm/vibe-bgm.mp3",
]


def main():
    rep = {"skill_root": str(ROOT), "python": sys.version.split()[0],
           "checks": [], "actions": [], "ready": False}

    ok_py = sys.version_info >= (3, 9)
    rep["checks"].append({"name": "Python ≥ 3.9", "ok": ok_py, "version": sys.version.split()[0]})
    if not ok_py:
        rep["actions"].append("升级 Python 到 3.9 以上")

    missing = [p for p in CORE if not (ROOT / p).exists()]
    rep["checks"].append({"name": "核心文件", "ok": not missing, "missing": missing})
    if missing:
        rep["actions"].append("技能目录不完整，缺：" + "、".join(missing))

    try:
        import PIL
        rep["checks"].append({"name": "Pillow", "ok": True, "version": getattr(PIL, "__version__", "?")})
    except Exception:
        rep["checks"].append({"name": "Pillow", "ok": False})
        rep["actions"].append("pip install pillow")

    fonts = {}
    try:
        from fonts import pick_font
        for kind in ("kai", "hei"):
            f, path, name = pick_font(kind, 40)
            fonts[kind] = str(path)
        rep["checks"].append({"name": "中文字体", "ok": True, "font": fonts})
    except SystemExit as e:
        rep["checks"].append({"name": "中文字体", "ok": False, "error": str(e)})
        rep["actions"].append("把一个中文 .ttf 放进 fonts/（推荐霞鹜文楷，OFL 可商用）")

    ff = shutil.which("ffmpeg")
    rep["checks"].append({"name": "ffmpeg（第 3 种才需要）", "ok": bool(ff),
                          "path": str(ff) if ff else None})

    try:
        import playwright  # noqa: F401
        has_pw = True
    except Exception:
        has_pw = False
    rep["checks"].append({"name": "playwright（第 3 种才需要）", "ok": has_pw})

    if not (ff and has_pw):
        rep["actions"].append("只做第 3 种才需要：pip install playwright && python -m playwright install chromium（外加 ffmpeg）")

    # 只有影响第 1、2 种的检查才决定 ready
    blocking = [c for c in rep["checks"]
                if not c["ok"] and "第 3 种" not in c["name"]]
    rep["ready"] = not blocking
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
