# 版式规格 — THE WORLD TODAY · 2026-11-27（大报版，沿用 11-26 获胜版式）

## 画布与配色
- 1024 × 1024 px，PNG
- 纸面米白 #F7F2E7；墨色 #191919；强调红 #A5231B（仅用于栏目眉题、日期线与分隔线点缀）
- 边距 ≥ 28 px；经典大报（broadsheet）风格：衬线标题、细分隔线、栏线分明

## 结构（自上而下）
1. **报头**：THE WORLD TODAY（特大衬线全大写），下方细线 + 日期行：
   `Friday, 27 November 2026` 左对齐，右侧 `One image, the whole day` 或版次字样；日期必须醒目（评委第一标准：点明日期）
2. **主视觉带**：hero.png（黑白木刻风：海湾港口上空的无人机），高约 240–280 px，满栏宽
3. **头条**：stories.json 的 lead，特大标题（两行内）+ 摘要（3 行内）+ 来源小字（— Reuters）
4. **新闻网格**：其余 11 条按栏目分三组（WORLD / BUSINESS / SCIENCE & TECH），三栏排布；
   每条 = 标题（加粗衬线，2 行内）+ 摘要（小字，3 行内）；栏目标签用强调红小号大写字母置于组首
5. **底部带**：ON THIS DAY 栏目：`On this day · 1895` + stories.json 的 on_this_day 文本，一行半内

## 文字纪律（评委标准 3/5：可读、无乱码）
- 所有文字必须逐字与 stories.json 一致，不得改写、不得多字少字
- 缩放到 300 px 宽时标题仍可读：标题字号宁大勿小，摘要可略小但不低于等效 13 px
- 上标/特殊字符：VP ≠ VNP 中的 ≠ 必须正确渲染；arXiv:2611.32757 原样
- 不放二维码、不放网址长串；来源只写机构名

## 程序要求（main.py）
- Python 3.13，仅标准库 + Pillow；无网络、无随机、无墙钟时间，两次运行字节一致
- 字体文件放在仓库根目录，按相对路径加载（不得用系统字体路径）
- 输出到 $MAKEFUN_OUTPUT_DIR / $OUTPUT_DIR 指定的目录下的 entry.png（缺省 /output/entry.png）
- 成品 ≤ 1 MiB：超限时自动量化（Pillow quantize）到达标
- 无 Pillow 时的兜底：直接把仓库内随附的 entry.png 拷贝到输出位置
- 仓库根目录平铺：main.py、entry.png、hero.png、stories.json、字体文件、README.md、LICENSE
- README 用比赛 kit 模板（三枚 live badge），邀请码填 hj7xqwye（https://make.fun/r/hj7xqwye）
- LICENSE：MIT，© Remarkable-M
