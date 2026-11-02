#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build.py — 把帧序列合成 mp4（可带配乐 / 旁白）。

    python scripts/build.py projects/xxx --fps 30
    python scripts/build.py projects/xxx --fps 30 --audio projects/xxx/audio/track.wav
    python scripts/build.py projects/xxx --fps 30 --crf 20 --keep-frames

音频比画面短就用静音补齐，长就裁到最后一帧——成片长度永远由画面决定，
不会被 `-shortest` 半路截断。音轨文件由 scripts/audio.py 生成（正好片长）。

产物：projects/xxx/out/xxx.mp4（H.264 + yuv420p，直接能上传）
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env  # noqa: E402  本机依赖路径，仓库里不写死


def find_ffmpeg():
    return env.ffmpeg()


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print("ffmpeg 失败：\n" + (p.stderr or "")[-1500:], file=sys.stderr)
        sys.exit(2)
    return p


def main():
    ap = argparse.ArgumentParser(description="帧序列 → mp4")
    ap.add_argument("project")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--audio", default=None, help="音轨 wav/mp3（audio.py 产的 audio/track.wav）；不给就是静音")
    ap.add_argument("--crf", type=int, default=18, help="画质，18 很清，23 体积小")
    ap.add_argument("--keep-frames", action="store_true", help="保留 png 帧（默认合成后删除）")
    ap.add_argument("--name", default=None, help="输出文件名，默认用目录名")
    args = ap.parse_args()

    project = Path(args.project)
    if not project.is_absolute():
        project = (Path.cwd() / project).resolve()
    frames = project / "frames"
    if not frames.exists() or not list(frames.glob("frame_*.*")):
        print("错误：没有帧。先跑 python scripts/render.py " + str(project) + " --fps " + str(args.fps), file=sys.stderr)
        sys.exit(2)

    # 自动识别帧序列：扩展名 + 起始编号（渲染中断、被外部删过都能接上）
    import re as _re
    pat = _re.compile(r"^frame_(\d+)\.(png|jpg)$")
    nums = []
    ext = None
    for f in frames.iterdir():
        m = pat.match(f.name)
        if m:
            nums.append(int(m.group(1)))
            ext = ext or m.group(2)
    if not nums:
        print("错误：frames 里没有 frame_XXXXX.png/jpg", file=sys.stderr)
        sys.exit(2)
    start_no = min(nums)

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("错误：找不到 ffmpeg。装一个，或把路径加到 PATH。", file=sys.stderr)
        sys.exit(2)

    outdir = project / "out"
    outdir.mkdir(parents=True, exist_ok=True)
    name = args.name or project.name
    mp4 = outdir / f"{name}.mp4"

    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(args.fps), "-start_number", str(start_no),
        "-i", str(frames / f"frame_%05d.{ext}"),
    ]
    if args.audio:
        a = Path(args.audio)
        if not a.is_absolute():
            a = (Path.cwd() / a).resolve()
        if not a.exists():
            print(f"错误：音频不存在 {a}", file=sys.stderr)
            sys.exit(2)
        video_seconds = len(nums) / float(args.fps)
        # apad：音频短了补静音；-t：长了一律裁到画面长度。
        # 不用 -shortest——那条会把画面也砍短，片尾直接没了。
        cmd += ["-i", str(a), "-af", "apad", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{video_seconds:.3f}"]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(mp4),
    ]
    run(cmd)

    guard = ""
    if len(nums) < (max(nums) - start_no + 1) * 0.9:
        guard = f"⚠ 帧不连贯（{len(nums)} 张，编号 {start_no}–{max(nums)}），成片可能短于预期。重渲染一次。\n"

    size = mp4.stat().st_size / 1e6
    print(f"成片：{mp4}")
    print(f"体积：{size:.1f} MB")
    if guard:
        print(guard)

    probe = env.ffmpeg("ffprobe") or str(Path(ffmpeg).with_name("ffprobe.exe" if sys.platform == "win32" else "ffprobe"))
    if Path(probe).exists():
        p = subprocess.run([probe, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
                            "-show_entries", "format=duration", "-of", "json", str(mp4)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            info = json.loads(p.stdout)
            s = info["streams"][0]
            print(f'规格：{s["width"]}×{s["height"]}  {s["r_frame_rate"]}  {float(info["format"]["duration"]):.1f}s')
        except Exception:
            pass

    if not args.keep_frames:
        n = 0
        for pat in ("frame_*.png", "frame_*.jpg"):
            for f in frames.glob(pat):
                f.unlink()
                n += 1
        print(f"已清理 {n} 张中间帧（要留着就加 --keep-frames）")


if __name__ == "__main__":
    main()
