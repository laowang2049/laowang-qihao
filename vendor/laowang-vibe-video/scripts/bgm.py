#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bgm.py — 用代码合成一段配乐，不需要任何外部音源。

⚠ 这条路**不是默认**：默认背景音是 assets/bgm/vibe-bgm.mp3（走 `audio.py default`）。
   它是第三个选项「系统自动配背景音」的引擎（`audio.py auto --mood calm|tense|bright`），
   也可以单独跑；别拿它顶替用户要的真音乐。

    python scripts/bgm.py projects/xxx/bgm.wav --duration 30
    python scripts/bgm.py projects/xxx/bgm.wav --duration 30 --mood calm
    python scripts/bgm.py projects/xxx/bgm.wav --duration 30 --mood tense --bpm 92

三种情绪：
    calm   安静、克制，适合讲解和收尾（大调，慢，只有铺底和弦 + 稀疏点音）
    tense  紧绷、推进，适合讲问题（小调，有低频脉冲和短促打击）
    bright 明亮、上扬，适合结论和号召（大调，加琶音）

说明：这是"能用的底噪级配乐"，不是作曲。它的作用是把静音感压下去，
让观众注意力停在画面上。真要更好听的音乐，得换真的生成器或用成曲。
"""

import argparse
import math
import struct
import wave

SR = 44100

MOODS = {
    "calm":   {"prog": [0, 5, 3, 4], "minor": False, "bpm": 68, "pad": 0.55, "pulse": 0.0, "arp": 0.0, "bright": 0.5},
    "tense":  {"prog": [0, 0, 5, 6], "minor": True,  "bpm": 88, "pad": 0.40, "pulse": 0.35, "arp": 0.0, "bright": 0.30},
    "bright": {"prog": [0, 4, 5, 3], "minor": False, "bpm": 96, "pad": 0.42, "pulse": 0.18, "arp": 0.30, "bright": 0.75},
}

ROOT = 220.0  # A3


def semis(n):
    return ROOT * (2 ** (n / 12.0))


def adsr(n, a, d, s, r, sr=SR):
    env = [0.0] * n
    na, nd, nr = int(a * sr), int(d * sr), int(r * sr)
    ns = max(0, n - na - nd - nr)
    i = 0
    for k in range(na):
        env[i] = k / max(1, na); i += 1
    for k in range(nd):
        env[i] = 1 - (1 - s) * (k / max(1, nd)); i += 1
    for k in range(ns):
        env[i] = s; i += 1
    for k in range(nr):
        if i >= n: break
        env[i] = s * (1 - k / max(1, nr)); i += 1
    return env


def add(buf, at, wave_data, gain=1.0):
    start = int(at * SR)
    end = min(len(buf), start + len(wave_data))
    for i in range(start, end):
        buf[i] += wave_data[i - start] * gain


def pad_voice(freq, dur, amp, detune=0.003):
    n = int(dur * SR)
    env = adsr(n, min(1.6, dur * 0.3), 0.3, 0.72, min(1.8, dur * 0.35))
    out = [0.0] * n
    for k in range(n):
        t = k / SR
        v = (math.sin(2 * math.pi * freq * t)
             + 0.42 * math.sin(2 * math.pi * freq * (1 + detune) * t)
             + 0.22 * math.sin(2 * math.pi * freq * 0.5 * t)
             + 0.10 * math.sin(2 * math.pi * freq * 2 * t))
        out[k] = v * env[k] * amp / 2.0
    return out


def pluck_voice(freq, dur, amp):
    n = int(dur * SR)
    env = adsr(n, 0.004, dur * 0.7, 0.0, dur * 0.28)
    out = [0.0] * n
    for k in range(n):
        t = k / SR
        v = math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(2 * math.pi * freq * 2 * t) \
            + 0.12 * math.sin(2 * math.pi * freq * 3.01 * t)
        out[k] = v * env[k] * amp
    return out


def main():
    ap = argparse.ArgumentParser(description="合成配乐")
    ap.add_argument("out")
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--mood", choices=list(MOODS), default="calm")
    ap.add_argument("--bpm", type=float, default=None)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gain", type=float, default=0.7, help="整体音量，0.7 大约 -3dB")
    args = ap.parse_args()

    cfg = MOODS[args.mood]
    bpm = args.bpm or cfg["bpm"]
    beat = 60.0 / bpm
    bar = beat * 4
    total = int(args.duration * SR)
    buf = [0.0] * total

    # 和弦铺底：每两小节换一次
    nb = int(math.ceil(args.duration / (bar * 2))) + 1
    for b in range(nb):
        deg = cfg["prog"][b % len(cfg["prog"])]
        base = semis(deg - 12)
        third = semis(deg - 12 + (3 if cfg["minor"] else 4))
        fifth = semis(deg - 12 + 7)
        at = b * bar * 2
        for f in (base, third, fifth):
            add(buf, at, pad_voice(f, bar * 2.1, cfg["pad"], detune=0.004), 0.5)

    # 低频脉冲（tense 明显）
    if cfg["pulse"] > 0:
        nbeats = int(args.duration / beat) + 1
        for i in range(nbeats):
            at = i * beat
            if at > args.duration:
                break
            env = adsr(int(0.34 * SR), 0.005, 0.2, 0.0, 0.12)
            n = len(env)
            v = [math.sin(2 * math.pi * semis(-24) * (k / SR)) * env[k] for k in range(n)]
            add(buf, at, v, cfg["pulse"] * 0.9)

    # 琶音（bright）
    if cfg["arp"] > 0:
        step = beat / 2
        notes = [0, 7, 12, 16, 12, 7]
        i = 0
        at = bar
        while at < args.duration:
            f = semis(notes[i % len(notes)] - 12)
            add(buf, at, pluck_voice(f, 0.9, 0.22), cfg["arp"])
            at += step
            i += 1

    # 轻噪声垫（空气感）
    rnd = args.seed * 2654435761
    for k in range(0, total, 1):
        if k % 7 == 0:
            rnd = (1103515245 * rnd + 12345) & 0x7FFFFFFF
            nz = (rnd / 0x7FFFFFFF - 0.5) * 0.006 * cfg["bright"]
            buf[k] += nz

    # 首尾淡入淡出
    fade_in, fade_out = int(1.2 * SR), int(1.5 * SR)
    for k in range(min(fade_in, total)):
        buf[k] *= k / fade_in
    for k in range(min(fade_out, total)):
        buf[total - 1 - k] *= k / fade_out

    peak = max(1e-9, max(abs(x) for x in buf))
    scale = (10 ** (-1.0 / 20.0)) * args.gain / peak

    path = args.out
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for x in buf:
            v = int(max(-1.0, min(1.0, x * scale)) * 32767)
            frames += struct.pack("<hh", v, v)
        w.writeframes(bytes(frames))

    print(f"配乐：{path}  {args.duration:.1f}s  {args.mood}  {bpm:.0f}BPM")
    print("提示：这是程序合成的底噪级配乐，作用是压住静音感；要更好听得换真生成器。")


if __name__ == "__main__":
    main()
