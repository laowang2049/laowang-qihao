#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""env.py — 找本机的 playwright 浏览器和 ffmpeg。

仓库里不写死任何绝对路径，别人 clone 下来也能直接跑。查找顺序：

  1. 环境变量（PLAYWRIGHT_BROWSERS_PATH / FFMPEG_PATH）
  2. 本机私有配置 config.local.json（已 .gitignore，不会进仓库）
  3. 常见安装位置
  4. PATH

依赖装在非标准位置时，在技能根目录放一个 config.local.json 就行：

    {"playwright_browsers": "D:/tools/ms-playwright",
     "ffmpeg_dir": "D:/tools/ffmpeg/bin"}

这个文件不会进仓库，别人也看不到。
"""

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = ROOT / "config.local.json"


def _conf():
    """本机私有配置，读不到就当空。"""
    try:
        return json.loads(CONF.read_text(encoding="utf-8"))
    except Exception:
        return {}


def browsers_path():
    """playwright 浏览器目录；找不到返回 None（交给 playwright 自己用默认位置）。"""
    c = _conf()
    cands = [
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH"),
        c.get("playwright_browsers"),
        str(Path.home() / ".cache" / "ms-playwright"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"),
        str(ROOT / ".cache" / "ms-playwright"),
    ]
    for p in cands:
        if p and Path(p).is_dir():
            return str(p)
    return None


def apply_browsers_path():
    """把找到的浏览器目录写进环境变量，供 playwright 使用。"""
    found = browsers_path()
    if found and not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = found
    return found


def ffmpeg(name="ffmpeg"):
    """找 ffmpeg / ffprobe 的可执行文件；找不到返回 None。"""
    exe = name + (".exe" if sys.platform == "win32" else "")
    c = _conf()
    cands = [os.environ.get(f"{name.upper()}_PATH"), c.get(name)]
    if c.get("ffmpeg_dir"):
        cands.append(str(Path(c["ffmpeg_dir"]) / exe))
    for p in cands:
        if p and Path(p).exists():
            return str(p)
    return shutil.which(name)


if __name__ == "__main__":
    print(json.dumps({
        "browsers": browsers_path(),
        "ffmpeg": ffmpeg(),
        "ffprobe": ffmpeg("ffprobe"),
    }, ensure_ascii=False, indent=1))
