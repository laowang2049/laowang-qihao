# 老王 vibe video

**给一个主题，出中文代码动画。** 341 种画风随便挑，画面是代码画的，不是拼素材。多长、横版竖版、背景音用哪首，你说了算。

> 老王 出品 · 抖音 @Agent老王

---

## 它怎么工作（五步，不用你操心）

0. **先问清四件事**：主题、多长（30 秒 / 1 分钟 / 2 分钟 / 自己填）、发哪儿（9:16 竖版 / 16:9 横版）、**背景音用哪个**（默认 vibe 增智小曲 / 自己上传 / 系统自动配）。你没说的一定会问，不会偷偷按 30 秒横版配程序音乐给你做。
1. **你说主题**（一句就行，例如"谣言为什么跑得比真相快"）。一时想不出来，它会推 3 个让你挑，也可以自己写。
2. **老王给你 3 个画风候选**，每条都把**预留画风图**直接发给你看，配一句话说明；没图的会明写「无预留画风图」。回 1/2/3 就选。
3. **都不满意？** 说一句"不满意"，本地会打开一张 341 全库的网页（纯静态，不用起服务）：按类别筛、搜关键词、点开看大图，挑好了点「就选这个画风」——**编号自动复制**，回对话窗口 Ctrl+V 粘过来就行，不用手抄。手机、平板也能直接翻：详情从底部弹出，「就选这个画风」一直钉在抽屉底部，不用往下扒拉。页面默认停在「O 奥斯卡 98 部」（98 条全部带预留图，最直观），想看全部点最左边的「全部」。
4. **问你要静帧还是全片**。静帧快，先看构图；全片慢，直接在 `projects/<名字>/out/` 出 mp4（尺寸按第 0 步定的来）。

成片不带任何水印，可以直接发。

## 装

```bash
# 1. 放到技能目录（或任意位置，只要能在那里执行命令）
# 2. 装两个依赖
pip install playwright --index-url https://mirrors.aliyun.com/pypi/simple/
python -m playwright install chromium      # 约 150MB，只需一次
# 3. 自检
python scripts/doctor.py                   # 看到 ready: true 就能用
python scripts/selftest.py                 # 可选：跑一遍整条链路（横版 + 竖版，都带背景音）
```

需要：Python 3.9+、ffmpeg（装好并加进 PATH）、中文字体（Windows 自带微软雅黑即可）。
不想装 playwright 也能用：选型页是纯静态 html，`library/picker.html` 双击就能翻。

依赖装在非标准位置（比如浏览器内核不在默认目录）时，在技能根目录放一个 `config.local.json`，这个文件已被 `.gitignore` 排除，不会进仓库：

```json
{"playwright_browsers": "D:/tools/ms-playwright", "ffmpeg_dir": "D:/tools/ffmpeg/bin"}
```

## 手动用（不走对话也行）

```bash
python scripts/style.py suggest --theme "谣言为什么传播得快"   # 看候选
python scripts/style.py get L36                               # 读某条画风的完整提示词
python scripts/picker.py                                      # 生成并打开 341 全库选型页（纯静态）
python scripts/new_project.py --theme "…" --style L36 --slug demo --duration 60 --size 9:16
python scripts/audio.py probe                                 # 三种背景音本机能不能用
python scripts/audio.py default --project projects/demo --duration 60   # 默认 vibe 增智小曲
python scripts/render.py projects/demo --still 2 6            # 先看静帧
python scripts/render.py projects/demo --fps 30 --audio projects/demo/audio/track.wav --build
```

背景音三条路，命令不一样而已，产物都是 `projects/demo/audio/track.wav`（正好片长、首尾淡入淡出）：

```bash
python scripts/audio.py default --project projects/demo --duration 60            # 内置小曲
python scripts/audio.py file    --project projects/demo --path "D:/m/x.mp3"       # 自己的素材
python scripts/audio.py auto    --project projects/demo --mood calm               # 现场合成
```

`auto` 三档情绪自己挑：`calm` 安静（讲原理、收尾）、`tense` 紧绷（讲问题、有冲突）、`bright` 明亮（讲结论、给号召）。

素材比片长短会整段循环接回去，长了就裁掉。想换默认小曲：拿你自己的音频覆盖 `assets/bgm/vibe-bgm.mp3`（或在 `config.local.json` 里写 `"bgm": "路径"`）。

`--size` 认 `9:16` / `16:9` 简写，也认 `1080x1920`、`1:1` 这类写法；`--duration` 直接给秒数。

## 341 画风库的真实情况（先看清楚再挑）

| | 数量 | 说明 |
|---|---|---|
| 总条目 | 341 | 每条一个 `.md` 提示词 |
| 带预览图 | 193 | 能先看到长什么样 |
| 提示词完整（≥600 字） | 232 | 能"严格照着做" |
| 提示词很短 | 47 | 只有一两句，细节得 AI 补 |
| 原库空条目 | 62 | 只有标题和分类，内容缺失（选型页默认隐藏 8 条完全空的） |

**既有图又提示词完整的有 166 条**，这是最稳的一档。K 卡通、V mg-styles、X code-video 三类基本没有预览图。

## 目录

```
SKILL.md              主流程（AI 看的）
scripts/              style / picker / new_project / render / build / audio / bgm / doctor / selftest
engine/               runtime.js（画布运行时）、template.html（舞台）、picker.tpl.html（选型页模板）
assets/bgm/           默认背景音「vibe 增智小曲」（vibe-bgm.mp3，可替换）
library/prompts/      341 条画风提示词 + 193 张预留画风图
library/index.json    索引（含 sha256，可校验有没有被改过）
library/picker.html   生成的选型页：纯静态，双击就能翻，点一下自动复制编号
knowledge/            分镜、动作、中文排版三篇判断方法
projects/             一条片子一个目录
picks/                你选过的画风记录
```

## 它不做什么

- 不做真人素材剪辑，也不做人声旁白（音轨只有背景音）。
- 不生成图片素材，画面全部由代码画。
- 背景音只有三条路：内置小曲 / 你上传的素材 / 现场合成。现场合成那条是 `bgm.py` 做的极简配乐，好听程度有限，要真音乐就上传。

## 出处

本版由 **老王** 重构：改成"主题 → 三候选 → 选型 → 静帧/全片"的固定流程，替换渲染引擎为 HTML+Canvas（原包的 TSX 组件不可直接运行），补齐可复现的出片链路、选型服务与自检。
第三方组件的许可与来源见 [NOTICE.md](NOTICE.md)。
