#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""style.py — 341 画风库的命令行接口。

老王 vibe video · 本文件是「AI 直接调用 341」的唯一入口。

用法（在技能根目录执行）：
    python scripts/style.py build                 重建索引（库文件变了才需要）
    python scripts/style.py stats                 库概况：多少条、多少有预览图
    python scripts/style.py list                  列出全部 341 条（--cat M 只看某类）
    python scripts/style.py search "工程 纸"       词面检索，返回候选
    python scripts/style.py get L36               读某条的完整提示词（AI 主要用这个）
    python scripts/style.py get L36 --meta-only   只看元信息，不读全文
    python scripts/style.py suggest --theme "……" 按主题给 3 个候选（AI 的第一步）
    python scripts/style.py verify                核对每个文件的 sha256 是否被改过

设计原则：
  · 只读，不改库；不改原文。
  · 每条都有 sha256，读全文时一并返回，方便在交付里记录「读的是哪一版」。
  · 输出默认是给人看的中文摘要；加 --json 输出机器可读结构。
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
PROMPTS = LIB / "prompts"
INDEX = LIB / "index.json"

CAT_LABEL = {
    "A-G_代码样片": "A–G 代码样片",
    "H_现成版式": "H 现成版式",
    "K_卡通画风": "K 卡通画风",
    "L_Lemo-Opuscar": "L Lemo-Opuscar",
    "M_动态风格": "M 动态风格",
    "O_奥斯卡98部": "O 奥斯卡 98 部",
    "R_照参考学来的": "R 照参考学来的",
    "V_mg-styles-15": "V mg-styles-15",
    "X_code-video": "X code-video",
    "Z_中国风": "Z 中国风",
}

# 「为什么 / 怎么办」这类疑问词切出来的二元组没有检索意义，丢掉
STOP_BIGRAM = {"什么", "为什", "怎么", "如何", "可以", "我们", "你们", "他们",
               "这个", "那个", "一个", "这样", "那样", "时候", "为什"}

# 主题词面完全没命中时的兜底三档：分属三个类别，差别足够大
FALLBACK_IDS = ["L36", "O10", "A3"]

# 抽象主题（"概率论有多反直觉"）很难和具体画风词面对上，
# 这里补几条「该往哪个方向挑」的软关键词，权重低，只做微调，不压过真正的词面命中
CONCEPT_HINTS = [
    (("原理", "机制", "科学", "数学", "物理", "算法", "为什么", "如何", "怎么",
      "本质", "是什么", "有多", "反直觉"),
     ["讲原理", "结构", "工程", "图解"]),
    (("历史", "年代", "古代", "从前", "百年", "战争", "王朝",
      "朝代", "宋朝", "唐朝", "明朝", "清朝", "汉代", "唐代", "宋代", "民国"),
     ["历史", "年代", "报纸", "档案"]),
    (("情绪", "孤独", "焦虑", "难过", "愤怒", "治愈", "内耗", "心事"),
     ["情绪", "内心", "孤独"]),
    (("数据", "统计", "增长", "下降", "经济", "商业", "公司", "钱", "概率"),
     ["数据", "图表", "统计"]),
    (("中国", "传统", "古诗", "节气", "国风", "民俗"),
     ["中国", "水墨", "民俗"]),
    (("宇宙", "星空", "时间", "自然", "海洋", "山脉"),
     ["宇宙", "星空", "自然"]),
    (("孩子", "可爱", "轻松", "搞笑", "日常"),
     ["卡通", "可爱", "手绘"]),
]


def concept_tokens(theme):
    out = []
    for triggers, hints in CONCEPT_HINTS:
        if any(t in theme for t in triggers):
            out.extend((h, 0.6) for h in hints)
    return out


def sha256_of(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def parse_entry(md_path):
    """从一个 .md 里抠出元信息和提示词正文。格式不统一，全部容错。"""
    raw = md_path.read_text(encoding="utf-8-sig", errors="replace")
    lines = raw.splitlines()

    m = re.match(r"^#\s*([A-Za-z0-9\-]+)\s*(.*)$", lines[0].strip()) if lines else None
    sid = m.group(1) if m else md_path.stem.split("_")[0]
    name = (m.group(2).strip() if m else "") or md_path.stem.split("_", 1)[-1]

    meta = {}
    for ln in lines[1:14]:
        mm = re.match(r"^-\s*([^：:]+)[：:]\s*(.*)$", ln.strip())
        if mm:
            meta.setdefault(mm.group(1).strip(), mm.group(2).strip())

    body = ""
    idx = raw.find("## 风格提示词")
    if idx >= 0:
        # 正文一直取到文件末尾：L 类提示词内部还有 ## 小节，不能按二级标题截断
        body = raw[idx + len("## 风格提示词"):].strip()
    else:
        body = "\n".join(lines[1:]).strip()

    n = len(body)
    quality = "full" if n >= 600 else ("short" if n >= 40 else "empty")

    jpg = md_path.with_suffix(".jpg")
    broken = (not name) and n == 0
    return {
        "id": sid,
        "name": name or "（原库未命名）",
        "broken": broken,
        "cat": md_path.parent.name,
        "cat_label": CAT_LABEL.get(md_path.parent.name, md_path.parent.name),
        "look": meta.get("长什么样") or meta.get("风格") or "",
        "fit": meta.get("适合", ""),
        "keywords": [k for k in re.split(r"[、，,\s]+", meta.get("关键词", "")) if k],
        "year": meta.get("年份", ""),
        "prompt_chars": n,
        "quality": quality,
        "md": md_path.relative_to(LIB).as_posix(),
        "still": jpg.relative_to(LIB).as_posix() if jpg.exists() else None,
        "sha256": sha256_of(md_path),
    }


def build_index():
    entries = []
    for md in sorted(PROMPTS.rglob("*.md")):
        entries.append(parse_entry(md))
    entries.sort(key=lambda e: (e["cat"], natural_key(e["id"])))
    data = {
        "schema": 1,
        "count": len(entries),
        "with_still": sum(1 for e in entries if e["still"]),
        "quality": {q: sum(1 for e in entries if e["quality"] == q) for q in ("full", "short", "empty")},
        "entries": entries,
    }
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def natural_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def load_index(auto_build=True):
    if not INDEX.exists():
        if auto_build:
            return build_index()
        sys.exit("索引不存在：先跑 python scripts/style.py build")
    return json.loads(INDEX.read_text(encoding="utf-8"))


def fmt_one(e, brief=False):
    tag = []
    if e["still"]:
        tag.append("有预览图")
    if e["quality"] == "empty":
        tag.append("提示词缺失")
    elif e["quality"] == "short":
        tag.append("提示词很短")
    head = f'{e["id"]}  {e["name"]}'
    if tag:
        head += "  [" + "/".join(tag) + "]"
    out = [head, f'  类别：{e["cat_label"]}']
    if e["look"]:
        out.append(f'  长什么样：{e["look"][:90]}')
    if e["fit"]:
        out.append(f'  适合：{e["fit"][:60]}')
    if brief:
        return "\n".join(out)
    out.append(f'  提示词：{e["prompt_chars"]} 字符  sha256:{e["sha256"][:12]}')
    return "\n".join(out)


def cmd_build(args):
    d = build_index()
    print(f'索引已重建：{d["count"]} 条，其中 {d["with_still"]} 条带预览图')
    q = d["quality"]
    print(f'提示词完整 {q["full"]} 条 / 很短 {q["short"]} 条 / 缺失 {q["empty"]} 条')
    print(f'写入 {INDEX.relative_to(ROOT).as_posix()}')


def cmd_stats(args):
    d = load_index()
    print(f'库版本：{d["count"]} 条画风，{d["with_still"]} 条带预览图')
    by = {}
    for e in d["entries"]:
        by.setdefault(e["cat_label"], [0, 0])
        by[e["cat_label"]][0] += 1
        by[e["cat_label"]][1] += 1 if e["still"] else 0
    for k, (n, s) in by.items():
        print(f"  {k:<22} {n:>3} 条  预览图 {s:>3}")
    q = d["quality"]
    print(f'提示词长度：完整 {q["full"]} · 很短 {q["short"]} · 缺失 {q["empty"]}')


def cmd_list(args):
    d = load_index()
    rows = d["entries"]
    if args.cat:
        c = args.cat.upper()
        rows = [e for e in rows if e["cat"].upper().startswith(c) or e["id"].upper().startswith(c)]
    if args.only_with_still:
        rows = [e for e in rows if e["still"]]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for e in rows:
        print(fmt_one(e, brief=True))


def tokens_of(text):
    """把中文查询切成「整词 + 二元字组」，解决不分词导致整串匹配不上的问题。"""
    words = [w for w in re.split(r"[\s,，、。；;：:！!？?“”\"'（）()]+", text) if w]
    out = []
    for w in words:
        out.append((w, 1.0))
        if len(w) >= 3:
            for i in range(len(w) - 1):
                bg = w[i:i + 2]
                if bg in STOP_BIGRAM:
                    continue
                out.append((bg, 0.5))
    seen, uniq = set(), []
    for t, wt in out:
        # 太短的英文词（a / of / 我们打的单字母）没意义；但 AI、3D、MG 这种两字缩写要留下
        if re.fullmatch(r"[a-z0-9]+", t) and len(t) < 3:
            continue
        if t and t not in seen:
            seen.add(t)
            uniq.append((t, wt))
    return uniq


def has_token(t, hay):
    """中文按子串匹配；英文/数字按整词匹配，否则 'ai' 会命中 'Painting'、'Kwai'。"""
    if not t:
        return False
    if re.fullmatch(r"[a-z0-9][a-z0-9 .\-+]*", t):
        return re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", hay) is not None
    return t in hay


def score_text(e, tokens):
    """词面贴合度。故意不给「有没有预览图」加分：图只影响观感，不影响贴不贴题。"""
    name = e["name"].lower()
    kw = " ".join(e["keywords"]).lower()
    look = (e["look"] or "").lower()
    fit = (e["fit"] or "").lower()
    cat = e["cat_label"].lower()
    s = 0.0
    hits = []
    for t, wt in tokens:
        t = t.lower()
        if not t:
            continue
        if has_token(t, name):
            s += 6 * wt
            hits.append(t)
        if has_token(t, kw):
            s += 4 * wt
            hits.append(t)
        if has_token(t, look):
            s += 2.5 * wt
            hits.append(t)
        if has_token(t, fit):
            s += 2.5 * wt
            hits.append(t)
        if has_token(t, cat):
            s += 1 * wt
    if e.get("broken"):
        s -= 30
    elif e["quality"] == "empty":
        s -= 8
    elif e["quality"] == "short":
        s -= 1.5
    return s, sorted(set(hits))


def cmd_search(args):
    d = load_index()
    tokens = tokens_of(args.query)
    rows = []
    for e in d["entries"]:
        s, hits = score_text(e, tokens)
        if s > 0:
            rows.append((s, e, hits))
    rows.sort(key=lambda x: (-x[0], x[1]["id"]))
    rows = rows[: args.n]
    if args.json:
        print(json.dumps([{**e, "score": round(s, 1), "hits": h} for s, e, h in rows], ensure_ascii=False, indent=1))
        return
    if not rows:
        print("没有命中。换更具体的词，或者用 list 浏览。")
        return
    for s, e, hits in rows:
        print(f"[{s:.1f}] " + fmt_one(e, brief=True))
        if hits:
            print("  命中：" + "、".join(hits))


def cmd_get(args):
    d = load_index()
    q = args.query.strip()
    cands = [e for e in d["entries"] if e["id"].upper() == q.upper()]
    if not cands:
        cands = [e for e in d["entries"] if q in e["name"] or e["id"].upper().startswith(q.upper())]
    if not cands:
        sys.exit(f"找不到「{q}」。用 search 或 list 找编号。")
    if len(cands) > 1 and not any(e["id"].upper() == q.upper() for e in cands):
        print("命中多条，请用编号重试：", file=sys.stderr)
        for e in cands[:10]:
            print("  " + fmt_one(e, brief=True), file=sys.stderr)
        sys.exit(1)
    e = cands[0]
    md = LIB / e["md"]
    body = md.read_text(encoding="utf-8-sig", errors="replace")

    if args.json:
        print(json.dumps({**e, "full_text": body}, ensure_ascii=False, indent=1))
        return
    if args.meta_only:
        print(fmt_one(e))
        return

    print("=" * 60)
    print(f'{e["id"]}  {e["name"]}')
    print(f'类别：{e["cat_label"]}')
    if e["look"]:
        print(f'长什么样：{e["look"]}')
    if e["fit"]:
        print(f'适合：{e["fit"]}')
    print(f'sha256：{e["sha256"]}')
    print(f'原文：library/{e["md"]}')
    if e["quality"] != "full":
        print("!")
        print("! 注意：这一条的提示词" + ("几乎是空的" if e["quality"] == "empty" else "很短") + "，")
        print("! 无法「严格按照提示词」执行，必须由你按名称和「长什么样」补设计，并告诉用户这一点。")
        print("!")
    print("=" * 60)
    print(body)


def still_abs(e):
    """预留画风图的绝对路径；这条没图就返回空串。"""
    return str((LIB / e["still"]).resolve()) if e.get("still") else ""


def cmd_suggest(args):
    d = load_index()
    n = args.n
    tokens = tokens_of(args.theme)
    extra = concept_tokens(args.theme)
    pool = [e for e in d["entries"] if not e.get("broken") and e["quality"] != "empty"]

    lexical = []
    for e in pool:
        s, hits = score_text(e, tokens)
        if s > 0:
            lexical.append([s, e, hits])
    lexical.sort(key=lambda r: (-r[0], r[1]["id"]))

    picked, cat_used = [], {}
    used = "lexical"

    def take(row, max_per_cat):
        e = row[1]
        if any(p[1]["id"] == e["id"] for p in picked):
            return
        if cat_used.get(e["cat"], 0) >= max_per_cat:
            return
        picked.append(row)
        cat_used[e["cat"]] = cat_used.get(e["cat"], 0) + 1

    def take_all(rows):
        # 先保证三个不同类别（差别才够大），不够再放宽到同类两条、最后不限
        for limit in (1, 2, n):
            for row in rows:
                if len(picked) == n:
                    return
                take(row, limit)

    take_all(lexical)
    lexical_n = len(picked)

    # 词面对上的不够 3 条：用「讲原理 / 历史 / 数据 …」这层方向词补位
    if len(picked) < n and extra:
        used = "mixed" if lexical_n else "concept"
        filled = []
        for e in pool:
            s, hits = score_text(e, extra)
            if s > 0:
                filled.append([s, e, hits])
        filled.sort(key=lambda r: (-r[0], r[1]["id"]))
        take_all(filled)

    if len(picked) < n:
        used = "fallback"
        for sid in FALLBACK_IDS:
            if len(picked) == n:
                break
            e = next((x for x in d["entries"] if x["id"] == sid), None)
            if e:
                take([0.0, e, []], n)

    if args.json:
        print(json.dumps(
            [{"id": e["id"], "name": e["name"], "cat": e["cat_label"], "look": e["look"],
              "fit": e["fit"], "has_still": bool(e["still"]), "still": e["still"],
              "still_abs": still_abs(e), "quality": e["quality"],
              "prompt_chars": e["prompt_chars"], "score": round(s, 1), "basis": used}
             for s, e, _ in picked],
            ensure_ascii=False, indent=1))
        return

    note = {
        "lexical": "按「贴不贴题」排的，没有因为「有没有预留图」加权。给用户之前自己再看一眼描述。",
        "mixed": "第一条词面对上了主题，其余按内容方向（讲原理 / 历史 / 数据…）补的。",
        "concept": "主题没有直接对上的画风，按内容方向（讲原理 / 历史 / 数据…）挑的，自己再判断一下。",
        "fallback": "主题词面几乎没命中，下面是三条通用款 —— 你自己判断贴不贴题，不合适就换掉。",
    }[used]
    print(f'主题：{args.theme}')
    print(note)
    print()
    for i, (s, e, hits) in enumerate(picked, 1):
        img = still_abs(e)
        print(f'[{i}] {e["id"]}  {e["name"]}  —— {"有预留画风图" if img else "无预留画风图"}')
        print(f'    类别：{e["cat_label"]} · 提示词 {e["prompt_chars"]} 字符 · 命中：{"、".join(hits) or "无（兜底）"}')
        if e["look"]:
            print(f'    长什么样：{e["look"][:110]}')
        if e["fit"]:
            print(f'    适合：{e["fit"][:70]}')
        print(f'    图：{img or "无（这条原库没配图，只能按描述判断）"}')
        print()
    print("给用户时：有图的把「图」的路径直接发出去让他看；没图的必须写明「无预留画风图」。")


def cmd_pick(args):
    """记录用户选了哪条，和选型页写的是同一个文件。"""
    from datetime import datetime
    d = load_index()
    q = args.id.strip()
    e = next((x for x in d["entries"] if x["id"].upper() == q.upper()), None)
    if not e:
        sys.exit(f"库里没有 {q}")
    picks = ROOT / "picks"
    picks.mkdir(exist_ok=True)
    rec = {
        "id": e["id"], "name": e["name"], "cat": e["cat_label"],
        "quality": e["quality"], "prompt_chars": e["prompt_chars"],
        "md": e["md"], "sha256": e["sha256"],
        "chosen_at": datetime.now().isoformat(timespec="seconds"),
        "stage": "style_chosen", "via": "cli",
    }
    (picks / "choice.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    with (picks / "history.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"已记录：{e['id']} {e['name']}（{e['cat_label']}）")
    print("下一步读全文：python scripts/style.py get " + e["id"])


def cmd_verify(args):
    d = load_index()
    bad = []
    for e in d["entries"]:
        md = LIB / e["md"]
        if not md.exists():
            bad.append((e["id"], "文件不见了"))
        elif sha256_of(md) != e["sha256"]:
            bad.append((e["id"], "内容被改过"))
    if bad:
        print(f"{len(bad)} 条不一致（跑 build 重建索引）：")
        for i, why in bad[:20]:
            print(f"  {i}: {why}")
        sys.exit(2)
    print(f'{d["count"]} 条全部与索引一致。')


def main():
    ap = argparse.ArgumentParser(description="341 画风库命令行接口")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build", help="重建索引").set_defaults(func=cmd_build)
    sub.add_parser("stats", help="库概况").set_defaults(func=cmd_stats)
    sub.add_parser("verify", help="校验 sha256").set_defaults(func=cmd_verify)

    p = sub.add_parser("list", help="列出条目")
    p.add_argument("--cat", help="只看某一类，例如 M / L / K")
    p.add_argument("--only-with-still", action="store_true", help="只看有预览图的")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("search", help="词面检索")
    p.add_argument("query")
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("get", help="读某条全文")
    p.add_argument("query", help="编号如 L36，或名称片段")
    p.add_argument("--meta-only", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("pick", help="记录用户选定的画风")
    p.add_argument("id")
    p.set_defaults(func=cmd_pick)

    p = sub.add_parser("suggest", help="按主题给候选")
    p.add_argument("--theme", required=True)
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_suggest)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
