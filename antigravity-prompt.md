# 给 Antigravity 的构建提示词（news-image-20261127 · 第一阶段：只构建，不提交）

你在一个全新的空文件夹里工作。用本仓库（Remarkable-M/world-today-20261127）素材包中的文件构建 make.fun 每日新闻图片赛的新一期参赛作品。

比赛：news-image-20261127「Sum up 27 November's world news in one image」，截止 2026-11-29T00:00:00Z（北京时间 11 月 29 日 08:00）。奖池 $100，前 50 名有奖。

## 账号纪律（重要）
- 沿用已有 make.fun 账号 @sunny-harbor-36-5689 与已有 keypair（C:\Users\R1396\.makefun\makefun-keypair.json）。
- 绝对不要生成新 keypair、不要注册新账号。

## 本阶段任务（只做构建，不要 submit）
按同目录下的 design-spec.md 与 stories.json，自己编写 main.py（Python 3.13，标准库 + Pillow），生成 entry.png：
- 1024×1024、≤1 MiB、确定性输出（两次运行字节一致）、无网络
- 所有新闻文字逐字取自 stories.json，不得改写
- 字体文件放仓库根目录、按相对路径加载；输出路径读 $MAKEFUN_OUTPUT_DIR / $OUTPUT_DIR，缺省 /output/entry.png
- 超 1 MiB 自动量化；无 Pillow 时兜底拷贝仓库内 entry.png
- 同时备好 README.md（kit 模板三 badge，邀请码 hj7xqwye）与 LICENSE（MIT，© Remarkable-M）
- 仓库根目录平铺，不要建子文件夹

## 自检（完成后逐项报告）
1. entry.png 尺寸与字节数；2. 用 main.py 实际运行两次，确认两次输出 sha256 一致；
3. 把 entry.png 缩到 300 px 宽自查标题可读、无溢出、无乱码（特别检查 ≠ 与 arXiv 编号）；
4. 对照 stories.json 逐条核对文字无误。

完成后停下来，把成品文件夹路径与自检结果报告给用户，不要执行 bundle / check / submit——提交是第二阶段的事。
