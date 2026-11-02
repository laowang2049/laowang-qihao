# 字体放这里

`scripts/fonts.py` 会优先用这个目录里的字体。空着也能跑（会用系统楷体）。

## 推荐：霞鹜文楷

- 协议：OFL，可商用、可再分发
- 下载：<https://github.com/lxgw/LxgwWenKai/releases>
- 放到这里：`fonts/LXGWWenKai-Regular.ttf`

它是模仿手写的楷体，做第 2 种（图文拼接）时最接近参考图的观感。

## 标题字体

文件名里带 `bold` / `hei` / `黑` / `heavy` 的，会被当成第 1 种（标题）用的粗黑体，
例如 `fonts/SourceHanSans-Bold.otf`。

## 支持的格式

`.ttf` `.otf` `.ttc`

字体文件不进 git（见 `.gitignore`），你本地放好就行。
