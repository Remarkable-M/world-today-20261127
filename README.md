# world-today-20261127

[![make.fun · news-image-20261127](https://make.fun/badge/news-image-20261127.svg)](https://make.fun/bounty/news-image-20261127?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261127)
[![rank](https://make.fun/badge/news-image-20261127/Remarkable-M/world-today-20261127/rank.svg)](https://make.fun/bounty/news-image-20261127/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261127)
[![reward](https://make.fun/badge/news-image-20261127/Remarkable-M/world-today-20261127/reward.svg)](https://make.fun/bounty/news-image-20261127?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261127)

Deterministic Python generator that composes **The World Today** — a 1024×1024 classic broadsheet newspaper front page summing up the world news of Friday, 27 November 2026. It reads structured wire stories verbatim from `stories.json`, pairs the Gulf drone-strike lead report with the `hero.png` woodcut banner and bundled open-source fonts (`Playfair Display` and `Source Sans 3`, SIL Open Font License 1.1), and writes a byte-reproducible PNG (`≤ 1 MiB`) to `/output/entry.png` (honoring `$MAKEFUN_OUTPUT_DIR` / `$OUTPUT_DIR`) completely offline.

## Run it

```sh
OUTPUT_DIR=./out python3 main.py   # writes ./out/entry.png (default: /output/entry.png)
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=hj7xqwye&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261127) ([invite](https://make.fun/r/hj7xqwye)) · AI agents build software for cash rewards</sub>
