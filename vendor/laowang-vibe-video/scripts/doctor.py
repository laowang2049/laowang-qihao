#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doctor.py — 开工前自检。

    python scripts/doctor.py

输出 JSON：ready 为 true 才能开工；false 时按 actions 修。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env  # noqa: E402  本机依赖路径，仓库里不写死

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
INDEX = LIB / "index.json"
CORE = [
    "SKILL.md",
    "engine/runtime.js",
    "engine/template.html",
    "engine/picker.tpl.html",
    "scripts/style.py",
    "scripts/render.py",
    "scripts/build.py",
    "scripts/bgm.py",
    "scripts/audio.py",
    "scripts/picker.py",
    "scripts/new_project.py",
    "scripts/env.py",
    "library/index.json",
    # 默认音轨（第 0 步四问里的「默认 vibe 增智小曲」）
    "assets/bgm/vibe-bgm.mp3",
]


def main():
    rep = {"skill_root": str(ROOT), "python": sys.version.split()[0], "checks": [], "actions": [], "ready": False}

    missing = [p for p in CORE if not (ROOT / p).is_file()]
    rep["checks"].append({"name": "核心文件", "ok": not missing, "missing": missing})
    if missing:
        rep["actions"].append("技能目录不完整，缺：" + "、".join(missing))

    # 341 库
    if INDEX.exists():
        try:
            idx = json.loads(INDEX.read_text(encoding="utf-8"))
            n = idx.get("count")
            stills = idx.get("with_still")
            real_md = len(list((LIB / "prompts").rglob("*.md")))
            ok = n == real_md
            rep["checks"].append({"name": "341 库", "ok": ok, "index": n, "files": real_md, "with_still": stills})
            if not ok:
                rep["actions"].append("索引和库文件数不一致：python scripts/style.py build")
        except Exception as e:
            rep["checks"].append({"name": "341 库", "ok": False, "error": repr(e)})
            rep["actions"].append("索引读不出来：python scripts/style.py build")
    else:
        rep["checks"].append({"name": "341 库", "ok": False, "error": "无 index.json"})
        rep["actions"].append("python scripts/style.py build")

    # playwright
    try:
        import playwright  # noqa: F401
        rep["checks"].append({"name": "playwright 包", "ok": True})
    except Exception:
        rep["checks"].append({"name": "playwright 包", "ok": False})
        rep["actions"].append("pip install playwright --index-url https://mirrors.aliyun.com/pypi/simple/")

    found = env.apply_browsers_path()
    if found:
        rep["checks"].append({"name": "浏览器内核", "ok": True, "path": found})
    else:
        rep["checks"].append({"name": "浏览器内核", "ok": False})
        rep["actions"].append("python -m playwright install chromium（约 150MB）")

    # ffmpeg
    ff = env.ffmpeg()
    rep["checks"].append({"name": "ffmpeg", "ok": bool(ff), "path": ff})
    if not ff:
        rep["actions"].append("装 ffmpeg 并加进 PATH；装在别处就在 config.local.json 里写 ffmpeg_dir")

    # ffprobe：音轨要读时长（一般跟 ffmpeg 一起装）
    fp = env.ffmpeg("ffprobe")
    rep["checks"].append({"name": "ffprobe", "ok": bool(fp), "path": fp})
    if not fp:
        rep["actions"].append("ffprobe 不在：音轨得先量长度，缺了 audio.py 跑不了（通常跟 ffmpeg 同一个目录）")

    # 中文字体（粗查）
    fonts = Path("C:/Windows/Fonts")
    has_cn = fonts.exists() and any((fonts / f).exists() for f in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf"))
    rep["checks"].append({"name": "中文字体", "ok": has_cn,
                          "note": "没有微软雅黑会回落，中文可能变方框" if not has_cn else ""})

    # 背景音：默认小曲要能用；自动配靠 scripts/bgm.py（纯 Python，不用装东西）
    try:
        import audio as audio_mod
        bgm = audio_mod.resolve_default_bgm()
        info = audio_mod.media_info(bgm) if bgm else None
        rep["checks"].append({"name": "默认背景音（vibe 增智小曲）", "ok": bool(bgm),
                              "path": str(bgm) if bgm else None,
                              "seconds": (info or {}).get("seconds")})
        if not bgm:
            rep["actions"].append("默认小曲不见了：assets/bgm/vibe-bgm.mp3（换曲子就放同名文件，"
                                  "或 config.local.json 里写 \"bgm\": \"路径\"）")
        rep["checks"].append({"name": "自动配背景音（bgm.py）", "ok": (ROOT / "scripts" / "bgm.py").is_file()})
    except Exception as e:
        rep["checks"].append({"name": "默认背景音（vibe 增智小曲）", "ok": False, "error": repr(e)})
        rep["actions"].append("scripts/audio.py 读不出来，先修这个文件")

    pick = ROOT / "picks" / "choice.json"
    if pick.exists():
        try:
            c = json.loads(pick.read_text(encoding="utf-8"))
            rep["checks"].append({"name": "上次选择", "ok": True, "style": c.get("id"), "title": c.get("name")})
        except Exception:
            pass

    # 可选能力（blocking: false）缺了不算不 ready：用户没选它就用不上
    rep["ready"] = (all(c.get("ok") for c in rep["checks"] if c.get("blocking", True))
                    and not rep["actions"])
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
