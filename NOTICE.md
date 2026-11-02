# 出处与许可

## 本仓库的构成

```
laowang-qihao/
  SKILL.md  README.md  scripts/  assets/  fonts/    老王原创
  vendor/laowang-vibe-video/                        内置的另一个技能（原样保留）
```

**两层署名，不混在一起：**

1. **老王原创部分**（三种起号流程、排版引擎 `scripts/`、文案提示词、示例图）——
   版权归老王，许可见 [LICENSE](LICENSE)。
2. **`vendor/laowang-vibe-video/`** —— 这是 [laowang-vibe-video] 的完整内置副本，
   它自己的 `NOTICE.md` 原样保留、一字未改，里面的第三方署名以那份为准。


## 产出物的归属

用本技能生成的图片、视频，**版权归使用者**，可自由商用、变现、二次发布。

本仓库的许可以只约束「技能代码与文档本身」，不主张对产出物的任何权利。

## 字体

本仓库**不附带任何字体文件**。`scripts/fonts.py` 按下面的顺序就地取用：

1. `fonts/` 目录里用户自己放的字体（推荐霞鹜文楷，OFL 协议，可商用）
2. 系统自带楷体 / 黑体（Windows `simkai.ttf`、macOS `Kaiti`、Linux `Noto Serif CJK`）

系统字体只在用户本机渲染时使用，不随本仓库分发。
