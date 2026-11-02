#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py — 一条命令验证「这台机器上整条链路能不能跑通」。

    python scripts/selftest.py

它会走一遍：选画风 → 读提示词 → 建项目 → 定背景音（默认小曲 / 自己上传 / 系统自动配）→
出静帧 → 出成片，最后核对 mp4 的规格和音轨，横版竖版各验一次。
临时项目建在 projects/_selftest*，**跑完（不管成功失败）都会删掉**，不留痕迹。
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env  # noqa: E402  本机依赖路径，仓库里不写死

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
TMP = ROOT / "projects" / "_selftest"        # 横版 16:9
TMP_V = ROOT / "projects" / "_selftest_v"    # 竖版 9:16
BGM = ROOT / "assets" / "bgm" / "vibe-bgm.mp3"


def sh(args, show=False):
    p = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(f"\n✗ 失败：{' '.join(args)}")
        print((p.stdout or "")[-800:])
        print((p.stderr or "")[-800:])
        raise SystemExit(1)
    if show:
        print((p.stdout or "").strip())
    return p.stdout


def step(name):
    print(f"· {name} … ", end="", flush=True)


def ok(msg=""):
    print("OK" + ("  " + msg if msg else ""))


def bad(msg):
    print("失败")
    print(msg)
    raise SystemExit(1)


def png_size(p):
    from PIL import Image
    with Image.open(p) as im:
        return im.size


def probe(mp4):
    """读 mp4 的宽高与时长；没有 ffprobe 就返回 None。"""
    exe = env.ffmpeg("ffprobe")
    if not exe:
        return None
    p = subprocess.run([exe, "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,nb_frames",
                        "-show_entries", "format=duration", "-of", "json", str(mp4)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        info = json.loads(p.stdout)
        s = info["streams"][0]
        return s["width"], s["height"], float(info["format"]["duration"]), s.get("nb_frames", "?")
    except Exception:
        return None


def has_audio(mp4):
    exe = env.ffmpeg("ffprobe")
    if not exe:
        return None
    p = subprocess.run([exe, "-v", "error", "-select_streams", "a:0",
                        "-show_entries", "stream=codec_name,duration", "-of", "json", str(mp4)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        s = json.loads(p.stdout)["streams"][0]
        return s.get("codec_name"), float(s.get("duration") or 0)
    except Exception:
        return None


def audio_seconds(wav):
    exe = env.ffmpeg("ffprobe")
    if not exe:
        return None
    p = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(wav)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return float(p.stdout.strip())
    except Exception:
        return None


def run():
    print("老王 vibe video · 自测\n")
    for d in (TMP, TMP_V):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

    step("自检依赖")
    rep = json.loads(sh(["scripts/doctor.py"]))
    if not rep.get("ready"):
        bad("按 doctor 的 actions 修：" + json.dumps(rep.get("actions"), ensure_ascii=False, indent=1))
    ok(f'python {rep["python"]}')

    step("默认背景音可用")
    if not BGM.exists():
        bad(f"默认小曲不在：{BGM}")
    ok(f"{BGM.stat().st_size / 1e6:.1f} MB")

    step("按主题给 3 个候选")
    cands = json.loads(sh(["scripts/style.py", "suggest", "--theme", "谣言为什么传播得快", "--json"]))
    if len(cands) != 3:
        bad(f"只给了 {len(cands)} 个")
    ok(" / ".join(c["id"] for c in cands))

    sid = cands[0]["id"]
    step(f"记录并读全文（{sid}）")
    sh(["scripts/style.py", "pick", sid])
    body = sh(["scripts/style.py", "get", sid])
    ok(f"{len(body)} 字")

    step("生成 341 选型页（静态 html）")
    sh(["scripts/picker.py", "--no-open"])
    page = ROOT / "library" / "picker.html"
    if not page.exists() or page.stat().st_size < 50000:
        bad("选型页没生成")
    html = page.read_text(encoding="utf-8", errors="replace")
    if "就选这个画风" not in html or "无预留画风图" not in html:
        bad("选型页内容不完整（复制按钮或占位文案缺失）")
    ok(f"{page.stat().st_size // 1024} KB")

    # ---------- 横版：默认小曲 + 全链路到 mp4 ----------
    step("建横版项目（16:9 / 3 秒）")
    sh(["scripts/new_project.py", "--theme", "自测主题", "--style", sid,
        "--slug", "_selftest", "--duration", "3", "--size", "16:9"])
    brief = json.loads((TMP / "brief.json").read_text(encoding="utf-8"))
    if (brief["width"], brief["height"]) != (1920, 1080):
        bad(f"brief 尺寸不对 {brief['width']}×{brief['height']}")
    ok("1920×1080")

    step("定背景音：默认 vibe 增智小曲")
    r = json.loads(sh(["scripts/audio.py", "default", "--project", "projects/_selftest", "--duration", "3"]))
    track = TMP / "audio" / "track.wav"
    if not track.exists():
        bad("没生成 audio/track.wav")
    if r.get("warnings"):
        bad("音轨有问题：" + "；".join(r["warnings"]))
    got = audio_seconds(track)
    if got is not None and not (2.7 < got < 3.3):
        bad(f"音轨 {got:.2f}s，不是片长 3s")
    if json.loads((TMP / "brief.json").read_text(encoding="utf-8"))["audio"]["mode"] != "default":
        bad("brief.json 没记上音轨模式")
    ok(f"{got:.2f}s · 源 {r['source_seconds']}s · {'循环' if r['looped'] else '裁切'}")

    step("出静帧")
    sh(["scripts/render.py", "projects/_selftest", "--still", "1.0"])
    png = TMP / "stills" / "still_01.00s.png"
    if not png.exists():
        bad("没生成静帧")
    if png_size(png) != (1920, 1080):
        bad(f"静帧尺寸 {png_size(png)}")
    ok(f"{png.stat().st_size // 1024} KB")

    step("出成片（3 秒，带音轨）")
    sh(["scripts/render.py", "projects/_selftest", "--fps", "30",
        "--audio", "projects/_selftest/audio/track.wav", "--build"])
    mp4 = TMP / "out" / "_selftest.mp4"
    if not mp4.exists():
        bad("没生成 mp4")
    ok(f"{mp4.stat().st_size / 1e6:.1f} MB")

    step("核对 mp4")
    info = probe(mp4)
    if info:
        w, h, dur, frames = info
        if (w, h) != (1920, 1080) or not (2.5 < dur < 3.6):
            bad(f"规格不对：{w}x{h} {dur}s")
        a = has_audio(mp4)
        if a is None:
            ok(f"{w}×{h} · {dur:.1f}s · {frames} 帧（没装 ffprobe，没查音轨）")
        else:
            if not (2.5 < a[1] < 3.6):
                bad(f"成片音轨 {a[1]:.2f}s 和画面 {dur:.2f}s 对不上")
            ok(f"{w}×{h} · {dur:.1f}s · {frames} 帧 · 音轨 {a[0]} {a[1]:.1f}s")
    else:
        ok("（没装 ffprobe，跳过细查）")

    # ---------- 竖版：验证画幅跟着 --size 走 + 用户自传音轨 ----------
    step("建竖版项目（9:16 / 3 秒）")
    sh(["scripts/new_project.py", "--theme", "竖版自测", "--style", sid,
        "--slug", "_selftest_v", "--duration", "3", "--size", "9:16"])
    brief = json.loads((TMP_V / "brief.json").read_text(encoding="utf-8"))
    if (brief["width"], brief["height"]) != (1080, 1920):
        bad(f"brief 尺寸不对 {brief['width']}×{brief['height']}")
    ok("1080×1920")

    step("定背景音：用户上传（拿内置小曲冒充长素材，验裁切）")
    r = json.loads(sh(["scripts/audio.py", "file", "--project", "projects/_selftest_v",
                       "--path", str(BGM), "--duration", "3"]))
    if not (TMP_V / "audio" / "track.wav").exists():
        bad("没生成 audio/track.wav")
    ok(f"源 {r['source_seconds']}s → 3s")

    step("出竖版静帧")
    sh(["scripts/render.py", "projects/_selftest_v", "--still", "1.0"])
    pngv = TMP_V / "stills" / "still_01.00s.png"
    if not pngv.exists():
        bad("没生成竖版静帧")
    if png_size(pngv) != (1080, 1920):
        bad(f"竖版静帧尺寸 {png_size(pngv)}，画布没跟着 SCENE.size 走")
    ok(f"{pngv.stat().st_size // 1024} KB")

    # 第三种背景音：程序现场合成，不需要任何素材
    step("定背景音：系统自动合成")
    r = json.loads(sh(["scripts/audio.py", "auto", "--project", "projects/_selftest_v",
                       "--mood", "bright", "--duration", "3"]))
    if not (TMP_V / "audio" / "track.wav").exists():
        bad("没合成 track.wav")
    got = audio_seconds(TMP_V / "audio" / "track.wav")
    if got is not None and not (2.7 < got < 3.3):
        bad(f"合成配乐 {got:.2f}s，不是片长 3s")
    ok(f"{got:.2f}s · {r['mood']}")


def main():
    # 自测会写 picks/choice.json，先把用户上次的真实选择留一份，跑完原样放回去
    picks = ROOT / "picks"
    keep = {}
    if picks.is_dir():
        for f in picks.iterdir():
            if f.is_file():
                keep[f.name] = f.read_bytes()
    try:
        run()
    finally:
        for d in (TMP, TMP_V):
            shutil.rmtree(d, ignore_errors=True)
        if picks.is_dir():
            shutil.rmtree(picks, ignore_errors=True)
        if keep:
            picks.mkdir(parents=True, exist_ok=True)
            for name, blob in keep.items():
                (picks / name).write_bytes(blob)
        for p in ROOT.rglob("__pycache__"):
            shutil.rmtree(p, ignore_errors=True)
    print("\n全部通过（横版 + 竖版，都带背景音）。可以开始做片了。")
    print(f"试一下：python scripts/picker.py   然后把 {ROOT / 'library' / 'picker.html'} 交给用户")


if __name__ == "__main__":
    main()
