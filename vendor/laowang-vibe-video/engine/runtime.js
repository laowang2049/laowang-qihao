/* runtime.js — 老王 vibe video 的公共运行时
 *
 * 所有函数都只依赖 t（秒），不读时钟、不用累加状态，任意帧可重放。
 * 页面里全局对象名是 LV（LaoWang Video）。
 *
 * 用法：<script src="runtime.js"></script> 之后直接 LV.xxx
 */
(function (global) {
  'use strict';

  const TAU = Math.PI * 2;

  /* ---------------- 时间与缓动 ---------------- */

  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));

  // t 在 [a,b) 区间内的进度，裁到 0..1
  const unit = (t, a, b) => (b <= a ? (t >= b ? 1 : 0) : clamp((t - a) / (b - a)));

  const mix = (a, b, p) => a + (b - a) * p;

  const ease = {
    linear: p => p,
    smooth: p => { p = clamp(p); return p * p * (3 - 2 * p); },
    inQuad: p => clamp(p) ** 2,
    outQuad: p => 1 - (1 - clamp(p)) ** 2,
    inCubic: p => clamp(p) ** 3,
    outCubic: p => 1 - (1 - clamp(p)) ** 3,
    inOutCubic: p => { p = clamp(p); return p < 0.5 ? 4 * p ** 3 : 1 - (-2 * p + 2) ** 3 / 2; },
    outExpo: p => (p >= 1 ? 1 : 1 - 2 ** (-10 * clamp(p))),
    outBack: p => { p = clamp(p); const c = 1.7; return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2; },
  };

  // 弹簧：解析解，无状态，任意 t 直接算
  // zeta = c / (2*sqrt(k*m))；zeta<1 过冲，=1 临界，>1 慢收敛
  function spring(t, { k = 140, c = 20, m = 1, v0 = 0 } = {}) {
    if (t <= 0) return 0;
    const w0 = Math.sqrt(k / m);
    const z = c / (2 * Math.sqrt(k * m));
    if (z < 1) {
      const wd = w0 * Math.sqrt(1 - z * z);
      const A = 1;
      const B = (z * w0 + v0) / wd;
      return 1 - Math.exp(-z * w0 * t) * (A * Math.cos(wd * t) + B * Math.sin(wd * t));
    }
    if (Math.abs(z - 1) < 1e-6) {
      return 1 - Math.exp(-w0 * t) * (1 + (w0 + v0) * t);
    }
    const r1 = -w0 * (z - Math.sqrt(z * z - 1));
    const r2 = -w0 * (z + Math.sqrt(z * z - 1));
    const c2 = (v0 - r1) / (r2 - r1);
    const c1 = 1 - c2;
    return 1 - (c1 * Math.exp(r1 * t) + c2 * Math.exp(r2 * t));
  }

  /* ---------------- 确定性随机 ---------------- */

  function hash2(x, y, seed = 0) {
    let h = 2166136261 ^ (seed | 0);
    h = Math.imul(h ^ (x | 0), 16777619);
    h = Math.imul(h ^ (y | 0), 16777619);
    h ^= h >>> 13; h = Math.imul(h, 1274126177); h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }

  const rng = (seed = 0) => (i) => hash2(i, 7, seed);

  // 平滑二维值噪声，用于纸纹、流动感
  function noise2(x, y, seed = 0) {
    const xi = Math.floor(x), yi = Math.floor(y);
    const xf = x - xi, yf = y - yi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = hash2(xi, yi, seed), b = hash2(xi + 1, yi, seed);
    const c = hash2(xi, yi + 1, seed), d = hash2(xi + 1, yi + 1, seed);
    return mix(mix(a, b, u), mix(c, d, u), v);
  }

  function fbm(x, y, seed = 0, oct = 3) {
    let v = 0, amp = 0.5, f = 1;
    for (let i = 0; i < oct; i++) { v += amp * noise2(x * f, y * f, seed + i * 31); amp *= 0.5; f *= 2; }
    return v;
  }

  /* ---------------- 字体与排版 ---------------- */

  const FONT = {
    // Windows 优先，Mac/Linux 兜底
    sans: '"Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif',
    serif: '"Source Han Serif SC", "Songti SC", "SimSun", "Noto Serif CJK SC", serif',
    disp: '"Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif',
    mono: '"Cascadia Mono", Consolas, "Noto Sans Mono CJK SC", monospace',
  };

  const fontStr = (size, weight = 400, family = FONT.sans) => `${weight} ${size}px ${family}`;

  // 中文按字断行：不切标点开头，不切数字中间
  function wrap(ctx, text, maxW) {
    const lines = [];
    let line = '';
    const noStart = '，。、；：？！）》」』】%”’…—,.!?;:)]}';
    for (const ch of Array.from(text)) {
      if (ch === '\n') { lines.push(line); line = ''; continue; }
      const test = line + ch;
      if (ctx.measureText(test).width > maxW && line) {
        if (noStart.includes(ch)) { line = test; continue; }   // 标点跟着上一行走
        lines.push(line);
        line = ch;
      } else {
        line = test;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  function text(ctx, str, o = {}) {
    const {
      x = 0, y = 0, size = 48, weight = 400, family = FONT.sans, color = '#fff',
      align = 'left', baseline = 'alphabetic', maxW = 0, lineHeight = 1.35,
      letterSpacing = 0, alpha = 1, shadow = null,
    } = o;
    ctx.save();
    ctx.globalAlpha *= alpha;
    ctx.font = fontStr(size, weight, family);
    ctx.textAlign = align;
    ctx.textBaseline = baseline;
    if (shadow) { ctx.shadowColor = shadow.color || 'rgba(0,0,0,.5)'; ctx.shadowBlur = shadow.blur || 12; ctx.shadowOffsetY = shadow.y || 0; }
    const lines = maxW ? wrap(ctx, str, maxW) : String(str).split('\n');
    lines.forEach((ln, i) => {
      const yy = y + i * size * lineHeight;
      if (letterSpacing) {
        // 手工字距：逐字画，居中时先算总宽
        const chars = Array.from(ln);
        const total = chars.reduce((s, c) => s + ctx.measureText(c).width + letterSpacing, 0) - letterSpacing;
        let xx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
        const prevAlign = ctx.textAlign;
        ctx.textAlign = 'left';
        for (const c of chars) { ctx.fillStyle = color; ctx.fillText(c, xx, yy); xx += ctx.measureText(c).width + letterSpacing; }
        ctx.textAlign = prevAlign;
      } else {
        ctx.fillStyle = color;
        ctx.fillText(ln, x, yy);
      }
    });
    ctx.restore();
    return lines.length * size * lineHeight;
  }

  /* 逐字/逐块揭示：返回每个字符的 alpha 与位移，给定 t 直接算 */
  function reveal(t, at, dur, n, { stagger = 0.04, rise = 1, easeFn = ease.outCubic } = {}) {
    return Array.from({ length: n }, (_, i) => {
      const p = unit(t, at + i * stagger, at + i * stagger + dur);
      const e = easeFn(p);
      return { p: e, alpha: e, dy: (1 - e) * rise };
    });
  }

  /* 字幕：屏幕层安全区，带一层柔和底 */
  function subtitle(ctx, str, t, o = {}) {
    const { w = 1920, h = 1080, at = 0, size = 46, maxW = null, color = '#fff', bottom = 0.10 } = o;
    const mw = maxW || w * 0.78;
    ctx.save();
    ctx.font = fontStr(size, 500, FONT.sans);
    const lines = wrap(ctx, str, mw);
    const lh = size * 1.42;
    const blockH = lines.length * lh;
    const yTop = h * (1 - bottom) - blockH;
    const a = clamp(unit(t, at, at + 0.45));
    ctx.globalAlpha = a;
    // 底衬：读得清，但不抢画面
    const pad = size * 0.42;
    roundRect(ctx, (w - mw) / 2 - pad, yTop - pad, mw + pad * 2, blockH + pad * 1.6, 18);
    ctx.fillStyle = 'rgba(8,10,14,.42)';
    ctx.fill();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    lines.forEach((ln, i) => {
      text(ctx, ln, {
        x: w / 2, y: yTop + lh * (i + 0.5), size, weight: 500, color,
        align: 'center', baseline: 'middle', alpha: 1,
      });
    });
    ctx.restore();
  }

  function roundRect(ctx, x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.arcTo(x + w, y, x + w, y + h, rr);
    ctx.arcTo(x + w, y + h, x, y + h, rr);
    ctx.arcTo(x, y + h, x, y, rr);
    ctx.arcTo(x, y, x + w, y, rr);
    ctx.closePath();
  }

  /* ---------------- 相机 ---------------- */

  // 2D 相机：screen = center + zoom*R*(world - cam)
  // 用 anchor 版本可以保证某个世界点始终落在指定屏幕点
  function camera(ctx, { x = 0, y = 0, zoom = 1, rot = 0, w = 1920, h = 1080 } = {}) {
    ctx.save();
    ctx.translate(w / 2, h / 2);
    if (rot) ctx.rotate(rot);
    ctx.scale(zoom, zoom);
    ctx.translate(-x, -y);
    return () => ctx.restore();
  }

  // 让世界点 anchor 落在屏幕点 screen 上所需的相机中心
  function camForAnchor(anchor, screen, { zoom = 1, rot = 0, w = 1920, h = 1080 } = {}) {
    const dx = screen.x - w / 2, dy = screen.y - h / 2;
    const cos = Math.cos(-rot), sin = Math.sin(-rot);
    return { x: anchor.x - (dx * cos - dy * sin) / zoom, y: anchor.y - (dx * sin + dy * cos) / zoom };
  }

  /* ---------------- 背景：颗粒、纸纹、流场 ---------------- */

  function grain(ctx, w, h, t, { alpha = 0.05, scale = 1, seed = 1 } = {}) {
    // 用小块噪声平铺，比逐像素快
    const cell = 96 * scale;
    ctx.save();
    ctx.globalAlpha = alpha;
    for (let y = 0; y < h; y += cell) {
      for (let x = 0; x < w; x += cell) {
        const n = fbm(x / 220, y / 220, seed, 2);
        const s = Math.floor(t * 12); // 每秒 12 次的颗粒抖动，像胶片
        const v = hash2(x * 0.5 + s, y * 0.5 - s, seed);
        ctx.fillStyle = v > 0.5 ? '#ffffff' : '#000000';
        ctx.globalAlpha = alpha * (0.4 + n * 0.9);
        ctx.fillRect(x, y, cell, cell);
      }
    }
    ctx.restore();
  }

  function paper(ctx, w, h, t, { base = '#f2ece1', ink = '#2b2620', seed = 7, speed = 0.06 } = {}) {
    ctx.save();
    ctx.fillStyle = base;
    ctx.fillRect(0, 0, w, h);
    const img = ctx.getImageData(0, 0, Math.min(w, 640), Math.min(h, 360));
    // 低分辨率噪声放大，够用且快
    const cw = 640, ch = 360;
    for (let y = 0; y < ch; y += 2) {
      for (let x = 0; x < cw; x += 2) {
        const n = fbm(x / 40 + t * speed, y / 40, seed, 3);
        if (n > 0.62) {
          ctx.globalAlpha = (n - 0.62) * 0.5;
          ctx.fillStyle = ink;
          ctx.fillRect(x * (w / cw), y * (h / ch), 2 * (w / cw) + 1, 2 * (h / ch) + 1);
        }
      }
    }
    ctx.restore();
    return img;
  }

  // 流场：确定性粒子，回到 t 直接算，不累积
  function flowField(ctx, t, o = {}) {
    const {
      w = 1920, h = 1080, count = 220, seed = 3, speed = 1,
      color = 'rgba(255,255,255,.35)', width = 1, life = 3.2, len = 46,
      fieldScale = 0.0016, drift = 0.15,
    } = o;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    for (let i = 0; i < count; i++) {
      const sx = hash2(i, 1, seed) * w;
      const sy = hash2(i, 2, seed) * h;
      const phase = hash2(i, 3, seed) * life;
      const tt = ((t * speed + phase) % life) / life;   // 0..1 生命周期，可循环
      let x = sx, y = sy;
      const steps = 8;
      ctx.beginPath();
      const fade = Math.sin(tt * Math.PI);
      ctx.globalAlpha = 0.10 + fade * 0.5;
      for (let s = 0; s <= steps; s++) {
        const ang = fbm(x * fieldScale, y * fieldScale, seed + 11, 2) * TAU * 2 + t * drift;
        x += Math.cos(ang) * (len / steps);
        y += Math.sin(ang) * (len / steps);
        if (s === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  /* ---------------- 画布 ---------------- */

  function canvas(id = 'c') {
    const cv = document.getElementById(id);
    const ctx = cv.getContext('2d');
    return { cv, ctx, w: cv.width, h: cv.height };
  }

  // 清屏并按场景调色
  function clear(ctx, w, h, color = '#0b0d12') {
    ctx.save();
    ctx.globalAlpha = 1;
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }

  const LV = {
    clamp, unit, mix, ease, spring, hash2, rng, noise2, fbm,
    FONT, fontStr, wrap, text, reveal, subtitle, roundRect,
    camera, camForAnchor, grain, paper, flowField, canvas, clear, TAU,
  };

  global.LV = LV;

  // 老项目里可能还留着水印节点（#wm），一律摘掉：成片不出现任何水印
  if (typeof document !== 'undefined') {
    const wm = document.getElementById('wm');
    if (wm) wm.remove();
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = LV;
})(typeof window !== 'undefined' ? window : globalThis);
