#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audio.py — 一条片子的背景音，三选一，最后都落成同一个文件。

三选一（第 0 步就要跟用户定下来，跟时长、画幅一个级别）：

  1）默认 vibe 增智小曲  → 内置 assets/bgm/vibe-bgm.mp3，按片长裁 / 循环
  2）自己上传            → 用户给的任意音频文件，按片长裁 / 循环
  3）系统自动配背景音    → 按片子情绪用程序合成一段（calm / tense / bright）

三条都不是人声旁白，只是背景音。

用法：

    python scripts/audio.py probe                     # 三种本机能不能用，先摆给用户看
    python scripts/audio.py default --project projects/demo --duration 60
    python scripts/audio.py file    --project projects/demo --path "D:/music/x.mp3"
    python scripts/audio.py auto    --project projects/demo --mood calm

产物固定是 `projects/<名>/audio/track.wav`（44.1kHz / 立体声 / 正好片长），
直接喂给：`render.py projects/<名> --fps 30 --audio projects/<名>/audio/track.wav --build`

`--duration` 不给就沿用 brief.json 里的时长。stdout 只输出一行 JSON，方便读。
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env  # noqa: E402  本机依赖路径，仓库里不写死

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
BGM_DIR = ROOT / "assets" / "bgm"
DEFAULT_BGM_NAME = "vibe-bgm.mp3"
SR = 44100

# 程序合成配乐的三档情绪（bgm.py 实现，这里只是转述给人看）
MOODS = {
    "calm": "安静、克制：适合讲原理、讲结构、收尾",
    "tense": "紧绷、推进：适合讲问题、讲代价、有冲突",
    "bright": "明亮、上扬：适合讲结论、给号召、轻松科普",
}
DEFAULT_MOOD = "calm"


def fail(msg, code=2):
    print("错误：" + msg, file=sys.stderr)
    sys.exit(code)


def out(obj):
    print(json.dumps(obj, ensure_ascii=False))
    return 0


def ffmpeg():
    exe = env.ffmpeg()
    if not exe:
        fail("找不到 ffmpeg。装一个并加进 PATH；装在别处就在 config.local.json 里写 ffmpeg_dir", 2)
    return exe


def ffprobe():
    return env.ffmpeg("ffprobe")


def media_info(path):
    """读时长/采样率/声道；读不出来返回 None。"""
    exe = ffprobe()
    if not exe:
        return None
    p = subprocess.run([exe, "-v", "error", "-show_entries",
                        "format=duration:stream=codec_name,sample_rate,channels",
                        "-of", "json", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        info = json.loads(p.stdout)
        s = info["streams"][0]
        return {"seconds": round(float(info["format"]["duration"]), 3),
                "codec": s.get("codec_name"),
                "sample_rate": int(s.get("sample_rate") or 0),
                "channels": int(s.get("channels") or 0)}
    except Exception:
        return None


def run_ff(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        fail("ffmpeg 失败：\n" + (p.stderr or "")[-1200:], 2)


def resolve_default_bgm():
    """默认小曲在哪。顺序：环境变量 → config.local.json → assets/bgm/vibe-bgm.mp3 → assets/bgm 下第一个音频。"""
    c = {}
    conf = ROOT / "config.local.json"
    if conf.exists():
        try:
            c = json.loads(conf.read_text(encoding="utf-8"))
        except Exception:
            c = {}
    for cand in (os.environ.get("LAOWANG_BGM"), c.get("bgm")):
        if cand and Path(cand).is_file():
            return Path(cand)
    named = BGM_DIR / DEFAULT_BGM_NAME
    if named.is_file():
        return named
    if BGM_DIR.is_dir():
        for p in sorted(BGM_DIR.iterdir()):
            if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"):
                return p
    return None


def project_dir(slug_or_path):
    p = Path(slug_or_path)
    if p.is_dir():
        return p.resolve()
    cand = ROOT / "projects" / slug_or_path
    if cand.is_dir():
        return cand.resolve()
    fail(f"项目目录不存在：{slug_or_path}（先跑 new_project.py 建项目）")


def read_brief(proj):
    f = proj / "brief.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def target_seconds(proj, duration):
    if duration and duration > 0:
        return float(duration)
    brief = read_brief(proj)
    d = brief.get("duration")
    if d and float(d) > 0:
        return float(d)
    fail("不知道片长：加 --duration 60，或在 brief.json 里写 duration")


def prepare(src, out_path, seconds, fade=True, gain_db=0.0):
    """任意音频 → 正好 seconds 秒的 wav。短了自动循环，长了自动裁，首尾淡入淡出。"""
    info = media_info(src)
    if not info:
        fail(f"读不出这个音频的时长，可能不是音频文件：{src}", 2)

    fi = min(1.0, seconds * 0.2) if fade else 0
    fo = min(1.5, seconds * 0.25) if fade else 0
    af = []
    if fi > 0:
        af.append(f"afade=t=in:st=0:d={fi:.2f}")
    if fo > 0:
        af.append(f"afade=t=out:st={max(0.0, seconds - fo):.2f}:d={fo:.2f}")
    if abs(gain_db) > 1e-6:
        af.append(f"volume={gain_db:.1f}dB")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
           "-stream_loop", "-1", "-i", str(src), "-t", f"{seconds:.3f}"]
    if af:
        cmd += ["-af", ",".join(af)]
    cmd += ["-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(out_path)]
    run_ff(cmd)

    got = media_info(out_path) or {}
    warn = []
    if abs((got.get("seconds") or 0) - seconds) > 0.25:
        warn.append(f"音轨 {got.get('seconds')}s，和片长 {seconds:.1f}s 对不上")
    return {"source_seconds": info["seconds"], "looped": info["seconds"] < seconds,
            "trimmed": info["seconds"] > seconds, "out_seconds": got.get("seconds"), "warnings": warn}


def save_brief_audio(proj, payload):
    f = proj / "brief.json"
    brief = read_brief(proj)
    if not brief:
        return
    a = brief.get("audio") if isinstance(brief.get("audio"), dict) else {}
    a.update(payload)
    a["prepared_at"] = datetime.now().isoformat(timespec="seconds")
    brief["audio"] = a
    f.write_text(json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- 三个模式

def mode_default(args):
    src = Path(args.path) if args.path else resolve_default_bgm()
    if args.path and not src.is_file():
        fail(f"--path 指的文件不存在：{src}", 2)
    if not src or not Path(src).is_file():
        fail("找不到默认小曲：assets/bgm/vibe-bgm.mp3 不在了。\n"
             "  换一首就把它放到 assets/bgm/ 下（或 config.local.json 里写 \"bgm\": \"路径\"），\n"
             "  或者改用 --path 指一个文件；要程序合成的就换 auto 模式。", 3)
    proj = project_dir(args.project)
    seconds = target_seconds(proj, args.duration)
    dst = proj / "audio" / "track.wav"
    r = prepare(src, dst, seconds, fade=not args.no_fade, gain_db=args.gain)
    save_brief_audio(proj, {"mode": "default", "source": str(src), "out": "audio/track.wav",
                            "seconds": round(seconds, 2)})
    return out({"ok": True, "mode": "default", "source": str(src), "out": str(dst),
                "seconds": round(seconds, 2), "source_seconds": r["source_seconds"],
                "looped": r["looped"], "trimmed": r["trimmed"], "warnings": r["warnings"]})


def mode_file(args):
    if not args.path:
        fail("--path 要给用户上传的音频文件", 2)
    src = Path(args.path)
    if not src.is_file():
        fail(f"音频不存在：{src}", 2)
    proj = project_dir(args.project)
    seconds = target_seconds(proj, args.duration)
    dst = proj / "audio" / "track.wav"
    r = prepare(src, dst, seconds, fade=not args.no_fade, gain_db=args.gain)
    if r["looped"]:
        r["warnings"].append(f"用户素材只有 {r['source_seconds']}s，短于片长，已整段循环接回（接缝没做交叉淡化）")
    save_brief_audio(proj, {"mode": "file", "source": str(src), "out": "audio/track.wav",
                            "seconds": round(seconds, 2)})
    return out({"ok": True, "mode": "file", "source": str(src), "out": str(dst),
                "seconds": round(seconds, 2), "source_seconds": r["source_seconds"],
                "looped": r["looped"], "trimmed": r["trimmed"], "warnings": r["warnings"]})


def mode_auto(args):
    """系统自动配背景音：交给 bgm.py 按情绪现场合成一段，不需要任何素材。"""
    engine = SCRIPTS / "bgm.py"
    if not engine.is_file():
        fail("自动配背景音的引擎不在：scripts/bgm.py", 3)
    mood = args.mood or DEFAULT_MOOD
    if mood not in MOODS:
        fail(f"--mood 只认 {' / '.join(MOODS)}，收到的是 {mood}", 2)

    proj = project_dir(args.project)
    seconds = target_seconds(proj, args.duration)
    dst = proj / "audio" / "track.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(engine), str(dst),
           "--duration", f"{seconds:.3f}", "--mood", mood]
    if args.bpm:
        cmd += ["--bpm", str(args.bpm)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 or not dst.exists():
        fail("合成配乐失败：\n" + ((p.stderr or p.stdout or "")[-900:]), 2)

    got = media_info(dst) or {}
    warn = []
    if abs((got.get("seconds") or 0) - seconds) > 0.3:
        warn.append(f"合成出来 {got.get('seconds')}s，和片长 {seconds:.1f}s 对不上")
    save_brief_audio(proj, {"mode": "auto", "source": f"bgm.py:{mood}", "out": "audio/track.wav",
                            "mood": mood, "bpm": args.bpm, "seconds": round(seconds, 2)})
    return out({"ok": True, "mode": "auto", "source": f"bgm.py:{mood}", "out": str(dst),
                "seconds": round(seconds, 2), "mood": mood, "bpm": args.bpm,
                "mood_hint": MOODS[mood], "warnings": warn})


def mode_probe(args):
    bgm = resolve_default_bgm()
    info = media_info(bgm) if bgm else None
    engine = SCRIPTS / "bgm.py"
    return out({
        "default_bgm": {
            "path": str(bgm) if bgm else None,
            "exists": bool(bgm),
            "seconds": (info or {}).get("seconds"),
            "codec": (info or {}).get("codec"),
        },
        "auto": {"available": engine.is_file(), "engine": str(engine) if engine.is_file() else None,
                 "moods": MOODS, "default_mood": DEFAULT_MOOD},
        "ffmpeg": env.ffmpeg(),
        "ffprobe": ffprobe(),
        "hint": "三条都是背景音，没有人声旁白：默认小曲看 default_bgm.exists，"
                "自动配看 auto.available，自己上传只要 ffmpeg 在就行。",
    })


def main():
    ap = argparse.ArgumentParser(description="背景音：默认小曲 / 自己上传 / 系统自动配")
    sub = ap.add_subparsers(dest="mode", required=True)

    p = sub.add_parser("probe", help="本机三种背景音方案的可用情况")
    p.set_defaults(func=mode_probe)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", required=True, help="项目目录或 slug")
    common.add_argument("--duration", type=float, default=None, help="片长（秒），不给就读 brief.json")
    common.add_argument("--gain", type=float, default=0.0, help="音量微调，单位 dB，负数更轻")
    common.add_argument("--no-fade", action="store_true", help="不要首尾淡入淡出")

    p = sub.add_parser("default", parents=[common], help="默认 vibe 增智小曲")
    p.add_argument("--path", default=None, help="临时换一首（默认用 assets/bgm/vibe-bgm.mp3）")
    p.set_defaults(func=mode_default)

    p = sub.add_parser("file", parents=[common], help="用户自己上传的背景音")
    p.add_argument("--path", required=True)
    p.set_defaults(func=mode_file)

    p = sub.add_parser("auto", parents=[common], help="系统自动配背景音（按情绪现场合成）")
    p.add_argument("--mood", default=DEFAULT_MOOD, choices=list(MOODS),
                   help="calm 安静 / tense 紧绷 / bright 明亮（默认 calm）")
    p.add_argument("--bpm", type=float, default=None, help="速度，不填按情绪自带的值")
    p.set_defaults(func=mode_auto)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
