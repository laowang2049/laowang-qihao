#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clean.py — 把测试/运行留下的东西清干净，回到可发布状态。

    python scripts/clean.py          # 只列出会删什么，不动手
    python scripts/clean.py --yes    # 真删

只动下面这些固定位置，绝不碰源文件：

    out/                                   底稿与成品（typeset / compose 写的）
    vendor/laowang-vibe-video/projects/     第 3 种建的项目（含成片）
    vendor/laowang-vibe-video/picks/        选型记录
    **/ __pycache__ /
    根目录的 draft.jpg / draft.json / final.jpg（旧版直接写在根上的）

发布前跑一次 `--yes`，再 `git status` 确认干净。
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIBE = ROOT / "vendor" / "laowang-vibe-video"

DIRS = [
    ROOT / "out",
    VIBE / "projects",
    VIBE / "picks",
]
STRAY = [ROOT / n for n in ("draft.jpg", "draft.json", "final.jpg", "final.png")]


def size_of(path):
    if path.is_file():
        return path.stat().st_size
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def main():
    ap = argparse.ArgumentParser(description="清理测试残留")
    ap.add_argument("--yes", action="store_true", help="真的删（不加只预览）")
    args = ap.parse_args()

    targets = [d for d in DIRS if d.exists()]
    targets += [f for f in STRAY if f.exists()]
    targets += [p for p in ROOT.rglob("__pycache__") if p.is_dir()]

    if not targets:
        print("已经是干净的，没东西要删。")
        return 0

    print("要清理的这些：")
    total = 0
    for t in targets:
        s = size_of(t)
        total += s
        print(f'  {t.relative_to(ROOT).as_posix():<48} {human(s)}')
    print(f'\n合计 {human(total)}')

    if not args.yes:
        print("\n这只是预览。确认要删就加 --yes。")
        return 0

    for t in targets:
        if t.is_dir():
            shutil.rmtree(t, ignore_errors=True)
        else:
            t.unlink(missing_ok=True)

    # 选型页会把「上次选了哪条」写进 html，删完 picks 要重建一次，否则发布出去的页面带着测试痕迹
    picker = VIBE / "scripts" / "picker.py"
    if picker.exists():
        subprocess.run([sys.executable, str(picker), "--no-open"],
                       cwd=str(VIBE), capture_output=True)
        print("已重建 vendor 里的选型页（清掉「当前已选」）")

    print("已清理。发布前记得 git status 看一眼。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
