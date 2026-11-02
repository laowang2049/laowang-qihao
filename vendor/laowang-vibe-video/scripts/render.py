#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render.py — 把 index.html 按时间轴逐帧截图。

静帧（先看构图）：
    python scripts/render.py projects/xxx --still 2.0 5.5 9.0

整片帧序列（再交给 build.py 合成 mp4）：
    python scripts/render.py projects/xxx --fps 30

常用参数：
    --duration 30   覆盖页面里的时长（一般不用，页面自己声明）
    --scale 0.5     半分辨率快速预览；正常出片不要带
    --out DIR       自定义输出目录

约定（AI 写页面时必须遵守）：
    window.__ready     字体与资源就绪后置 true
    window.__duration  全片秒数
    window.render(t)   画第 t 秒，只由 t 决定
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env  # noqa: E402  本机依赖路径，仓库里不写死

ROOT = Path(__file__).resolve().parent.parent


def fail(msg, code=2):
    print("错误：" + msg, file=sys.stderr)
    sys.exit(code)


def show_path(p, project):
    """日志用：落在项目里就显示相对路径，否则显示绝对路径，绝不抛异常。

    --out 可以是项目外、甚至相对路径；这里不能让它把已经成功的渲染带崩。
    """
    try:
        return p.resolve().relative_to(project).as_posix()
    except ValueError:
        return str(p)


def open_page(project_dir, width, height, scale):
    # 先定好浏览器目录，再让 playwright 起驱动，否则它只会找默认位置
    found = env.apply_browsers_path()
    if found:
        print(f"浏览器：{found}")
    from playwright.sync_api import sync_playwright

    index = project_dir / "index.html"
    if not index.exists():
        fail(f"{index} 不存在。项目里必须有 index.html（可从 engine/template.html 复制）")

    runtime = project_dir / "runtime.js"
    if not runtime.exists():
        src = ROOT / "engine" / "runtime.js"
        runtime.write_bytes(src.read_bytes())
        print("已把 engine/runtime.js 复制进项目")

    pw = sync_playwright().start()
    browser = pw.chromium.launch(args=[
        "--font-render-hinting=none",
        "--force-color-profile=srgb",
        "--allow-file-access-from-files",
        "--disable-lcd-text",
    ])
    vw, vh = int(width * scale), int(height * scale)
    page = browser.new_page(viewport={"width": vw, "height": vh}, device_scale_factor=1)

    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console." + m.type + ": " + m.text) if m.type == "error" else None)

    page.goto(index.resolve().as_uri() + "?render=1")
    try:
        page.wait_for_function("window.__ready === true", timeout=20000)
    except Exception:
        msg = "\n".join(errors[-6:]) or "页面没有把 window.__ready 置为 true"
        fail("页面没准备好：\n" + msg)

    duration = page.evaluate("window.__duration || 0")
    size = page.evaluate(
        "window.__size || (() => { const c = document.getElementById('c');"
        " return c ? [c.width, c.height] : null; })()")
    if errors:
        print("页面报错（先修这些再出片）：")
        for e in errors[-8:]:
            print("  · " + e)
    return pw, browser, page, float(duration), size


def main():
    ap = argparse.ArgumentParser(description="逐帧渲染")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--still", nargs="+", type=float, help="截几个时刻的静帧，单位秒")
    g.add_argument("--fps", type=int, help="输出整片帧序列")
    ap.add_argument("project", help="项目目录（含 index.html）")
    ap.add_argument("--duration", type=float, default=None, help="秒；默认读页面")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--audio", default=None, help="配合 --build：直接合成带这个音频的 mp4")
    ap.add_argument("--build", action="store_true", help="渲染完立刻合成 mp4（推荐，一步到位）")
    ap.add_argument("--keep-frames", action="store_true")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    project = Path(args.project)
    if not project.is_absolute():
        project = (Path.cwd() / project).resolve()
    if not project.exists():
        fail(f"项目目录不存在：{project}")

    brief = project / "brief.json"
    if brief.exists():
        try:
            b = json.loads(brief.read_text(encoding="utf-8"))
            args.width = int(b.get("width") or args.width)
            args.height = int(b.get("height") or args.height)
        except Exception:
            pass

    pw, browser, page, page_duration, page_size = open_page(project, args.width, args.height, args.scale)
    duration = args.duration or page_duration
    t_start = time.time()

    try:
        # 画面尺寸必须和 brief.json 一致，否则出片会被裁一刀（竖版尤其容易踩）
        if page_size and (int(page_size[0]) != args.width or int(page_size[1]) != args.height):
            fail(f"画面是 {page_size[0]}×{page_size[1]}，项目声明的是 {args.width}×{args.height}。\n"
                 f"  改 {project / 'index.html'} 里的 SCENE.size，或删掉项目用 --size 重建。")
        if args.still:
            outdir = Path(args.out) if args.out else project / "stills"
            outdir.mkdir(parents=True, exist_ok=True)
            for at in args.still:
                if duration and at > duration:
                    print(f"跳过 {at}s：超出片长 {duration}s")
                    continue
                page.evaluate(f"window.render({at})")
                page.wait_for_timeout(60)
                p = outdir / f"still_{at:05.2f}s.png"
                page.screenshot(path=str(p), clip={"x": 0, "y": 0, "width": args.width * args.scale, "height": args.height * args.scale})
                print(f"静帧 {show_path(p, project)}   {at}s")
            print("完成。先看这几张，再决定改哪里。")
        else:
            if not duration:
                fail("页面没有声明 window.__duration，无法确定片长")
            outdir = Path(args.out) if args.out else project / "frames"
            outdir.mkdir(parents=True, exist_ok=True)
            for pat in ("frame_*.png", "frame_*.jpg"):
                for old in outdir.glob(pat):
                    old.unlink()
            total = max(1, round(duration * args.fps))
            for i in range(total):
                t = i / args.fps
                page.evaluate(f"window.render({t})")
                page.screenshot(path=str(outdir / f"frame_{i:05d}.jpg"), quality=92, type="jpeg",
                                clip={"x": 0, "y": 0, "width": args.width * args.scale, "height": args.height * args.scale})
                if i % 30 == 0 or i == total - 1:
                    el = time.time() - t_start
                    print(f"\r帧 {i + 1}/{total}  已用 {el:.0f}s", end="", flush=True)
            print()
            print(f"完成：{total} 帧 → {show_path(outdir, project)}  （{time.time() - t_start:.0f}s）")
            if args.build:
                import subprocess
                cmd = [sys.executable, str(ROOT / "scripts" / "build.py"), str(project), "--fps", str(args.fps)]
                if args.audio:
                    cmd += ["--audio", str(Path(args.audio).resolve() if not Path(args.audio).is_absolute() else args.audio)]
                if args.keep_frames:
                    cmd += ["--keep-frames"]
                print("开始合成…")
                r = subprocess.run(cmd)
                if r.returncode != 0:
                    sys.exit(r.returncode)
            else:
                print(f"下一步：python scripts/build.py {args.project} --fps {args.fps}")
    finally:
        browser.close()
        pw.stop()


if __name__ == "__main__":
    main()
