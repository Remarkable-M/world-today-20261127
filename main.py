#!/usr/bin/env python3
"""Deterministic 1024x1024 broadsheet renderer for 'The World Today' (2026-11-27)."""

from __future__ import annotations

import io
import json
import os
import shutil
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    HAS_PIL = True
except ModuleNotFoundError:
    HAS_PIL = False

CANVAS_W = 1024
CANVAS_H = 1024
MAX_BYTES = 1_048_576
MARGIN = 28  # >= 28 px on all four sides

PAPER = "#F7F2E7"
PAPER_RGB = (247, 242, 231)
INK = "#191919"
INK_RGB = (25, 25, 25)
RED = "#A5231B"
HAIRLINE_DARK = "#191919"
HAIRLINE_MUTED = "#B8AFA0"

SECTION_GROUPS = ["WORLD", "BUSINESS", "SCIENCE & TECH"]


class FontBank:
    """Loads bundled TrueType fonts strictly by relative path from the repository root."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
        self._missing_in_serif: dict[str, bool] = {}
        self.files = {
            "serif_bold": base_dir / "PlayfairDisplay-Bold.ttf",
            "sans_reg": base_dir / "SourceSans3-Regular.ttf",
            "sans_semi": base_dir / "SourceSans3-SemiBold.ttf",
            "sans_bold": base_dir / "SourceSans3-Bold.ttf",
            "sans_italic": base_dir / "SourceSans3-Italic.ttf",
        }
        for path in self.files.values():
            if not path.is_file():
                raise FileNotFoundError(f"Missing bundled font file: {path}")
        probe = self.get("serif_bold", 24)
        self._serif_notdef = bytes(probe.getmask("\uffff"))

    def get(self, key: str, size: int) -> ImageFont.FreeTypeFont:
        cache_key = (key, size)
        if cache_key not in self._cache:
            self._cache[cache_key] = ImageFont.truetype(str(self.files[key]), size)
        return self._cache[cache_key]

    def serif_lacks_glyph(self, ch: str) -> bool:
        if ch in (" ", "\t", "\n"):
            return False
        if ch not in self._missing_in_serif:
            probe = self.get("serif_bold", 24)
            self._missing_in_serif[ch] = bytes(probe.getmask(ch)) == self._serif_notdef
        return self._missing_in_serif[ch]


def split_font_runs(text: str, fonts: FontBank, primary_key: str) -> list[tuple[str, str]]:
    """Splits text into (segment, font_key) runs so symbols like '≠' never render as .notdef."""
    if primary_key != "serif_bold":
        return [(text, primary_key)]
    runs: list[tuple[str, str]] = []
    buf: list[str] = []
    cur_key = primary_key
    for ch in text:
        target_key = "sans_bold" if fonts.serif_lacks_glyph(ch) else primary_key
        if buf and target_key != cur_key:
            runs.append(("".join(buf), cur_key))
            buf = [ch]
            cur_key = target_key
        else:
            if not buf:
                cur_key = target_key
            buf.append(ch)
    if buf:
        runs.append(("".join(buf), cur_key))
    return runs


def measure_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    fonts: FontBank,
    font_key: str,
    size: int,
) -> float:
    runs = split_font_runs(text, fonts, font_key)
    if len(runs) == 1 and runs[0][1] == font_key:
        return float(draw.textlength(text, font=fonts.get(font_key, size)))
    total = 0.0
    for seg, fkey in runs:
        total += float(draw.textlength(seg, font=fonts.get(fkey, size)))
    return total


def draw_text_line(
    draw: ImageDraw.ImageDraw,
    x: float,
    y_top: float,
    text: str,
    fonts: FontBank,
    font_key: str,
    size: int,
    fill: str,
) -> float:
    """Draws a single line of text anchored to primary baseline and returns its advance width."""
    primary_font = fonts.get(font_key, size)
    ascent, _ = primary_font.getmetrics()
    baseline_y = y_top + ascent
    runs = split_font_runs(text, fonts, font_key)
    if len(runs) == 1 and runs[0][1] == font_key:
        draw.text((round(x), round(baseline_y)), text, font=primary_font, fill=fill, anchor="ls")
        return float(draw.textlength(text, font=primary_font))

    cur_x = float(x)
    for seg, fkey in runs:
        rfont = fonts.get(fkey, size)
        draw.text((round(cur_x), round(baseline_y)), seg, font=rfont, fill=fill, anchor="ls")
        cur_x += float(draw.textlength(seg, font=rfont))
    return cur_x - float(x)


def wrap_words(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: float,
    fonts: FontBank,
    font_key: str,
    size: int,
    balanced: bool = False,
) -> list[str]:
    words = text.split()
    if not words:
        return []
    greedy: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if measure_text(draw, candidate, fonts, font_key, size) <= max_w:
            current = candidate
        else:
            greedy.append(current)
            current = word
    greedy.append(current)
    if not balanced or len(greedy) <= 1:
        return greedy

    target_lines = len(greedy)
    n = len(words)
    widths = [[0.0] * n for _ in range(n)]
    for i in range(n):
        seg = words[i]
        widths[i][i] = measure_text(draw, seg, fonts, font_key, size)
        for j in range(i + 1, n):
            seg = f"{seg} {words[j]}"
            widths[i][j] = measure_text(draw, seg, fonts, font_key, size)

    inf = 1e18
    dp: list[list[tuple[float, int]]] = [[(inf, -1)] * (target_lines + 1) for _ in range(n + 1)]
    dp[n][0] = (0.0, n)

    for k in range(1, target_lines + 1):
        for i in range(n - 1, -1, -1):
            best_cost = inf
            best_next = -1
            for j in range(i, n - k + 1):
                w = widths[i][j]
                if w > max_w + 0.5:
                    if j > i:
                        break
                    continue
                rem_cost, _ = dp[j + 1][k - 1]
                if rem_cost >= inf:
                    continue
                slack = max(0.0, max_w - w)
                if k == 1:
                    orphan_pen = (
                        (max_w * 0.36 - w) ** 2 * 4.0 if (j == i and w < max_w * 0.36) else 0.0
                    )
                    line_cost = slack * slack * 0.22 + orphan_pen
                else:
                    line_cost = slack * slack
                total = line_cost + rem_cost
                if total < best_cost:
                    best_cost = total
                    best_next = j + 1
            dp[i][k] = (best_cost, best_next)

    if dp[0][target_lines][0] >= inf:
        return greedy

    result: list[str] = []
    idx = 0
    for k in range(target_lines, 0, -1):
        nxt = dp[idx][k][1]
        result.append(" ".join(words[idx:nxt]))
        idx = nxt
    return result


def fit_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: float,
    fonts: FontBank,
    font_key: str,
    max_size: int,
    min_size: int,
    max_lines: int,
    min_lines: int = 1,
    balanced: bool = False,
) -> tuple[int, list[str]]:
    fallback_pair: tuple[int, list[str]] | None = None
    for size in range(max_size, min_size - 1, -1):
        lines = wrap_words(draw, text, max_w, fonts, font_key, size, balanced=balanced)
        if len(lines) <= max_lines and all(
            measure_text(draw, ln, fonts, font_key, size) <= max_w + 0.5 for ln in lines
        ):
            if len(lines) >= min_lines:
                return size, lines
            if fallback_pair is None:
                fallback_pair = (size, lines)
    if fallback_pair is not None:
        return fallback_pair
    lines = wrap_words(draw, text, max_w, fonts, font_key, min_size, balanced=balanced)
    return min_size, lines


def fit_single_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: float,
    fonts: FontBank,
    font_key: str,
    max_size: int,
    min_size: int = 10,
) -> int:
    for size in range(max_size, min_size - 1, -1):
        if measure_text(draw, text, fonts, font_key, size) <= max_w:
            return size
    return min_size


def prepare_hero_banner(hero_path: Path, target_w: int, target_h: int) -> Image.Image:
    """Crops hero.png to its woodcut frame and maps paper/ink cleanly to #F7F2E7 / #191919."""
    with Image.open(hero_path) as raw:
        gray = raw.convert("L")
    w, h = gray.size
    # Detect woodcut black frame edges deterministically so outer paper flecks are excluded
    left = 0
    for x in range(min(160, w // 4)):
        col = gray.crop((x, h // 6, x + 1, h - h // 6)).tobytes()
        if sum(1 for p in col if p < 80) > len(col) * 0.55:
            left = x
            break
    right = w
    for x in range(w - 1, max(w - 160, w * 3 // 4), -1):
        col = gray.crop((x, h // 6, x + 1, h - h // 6)).tobytes()
        if sum(1 for p in col if p < 80) > len(col) * 0.55:
            right = x + 1
            break
    top = 0
    for y in range(min(140, h // 4)):
        row = gray.crop((w // 6, y, w - w // 6, y + 1)).tobytes()
        if sum(1 for p in row if p < 80) > len(row) * 0.55:
            top = y
            break
    bottom = h
    for y in range(h - 1, max(h - 140, h * 3 // 4), -1):
        row = gray.crop((w // 6, y, w - w // 6, y + 1)).tobytes()
        if sum(1 for p in row if p < 80) > len(row) * 0.55:
            bottom = y + 1
            break

    cropped = gray.crop((left, top, right, bottom))
    resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
    lut: list[int] = []
    for v in range(256):
        if v >= 208:
            lut.append(255)
        elif v <= 36:
            lut.append(0)
        else:
            lut.append(round((v - 36) * 255 / 172))
    leveled = resized.point(lut)
    return ImageOps.colorize(leveled, black=INK_RGB, white=PAPER_RGB)


def render_front_page(base_dir: Path) -> bytes:
    stories_path = base_dir / "stories.json"
    hero_path = base_dir / "hero.png"
    data = json.loads(stories_path.read_text(encoding="utf-8"))

    fonts = FontBank(base_dir)
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), PAPER_RGB)
    draw = ImageDraw.Draw(img)

    left_x = MARGIN
    right_x = CANVAS_W - MARGIN
    content_w = right_x - left_x  # 968 px

    # =========================================================================
    # 1. MASTHEAD (y = 28 .. 109)
    # =========================================================================
    y = MARGIN  # 28
    draw.rectangle([left_x, y, right_x, y + 1], fill=RED)
    upper_rule_y = y + 4  # 32
    draw.line([(left_x, upper_rule_y), (right_x, upper_rule_y)], fill=HAIRLINE_DARK, width=1)

    nameplate_bottom_rule = y + 51  # 79
    masthead_title = data["masthead"]
    mast_size = fit_single_line(draw, masthead_title, content_w - 40, fonts, "serif_bold", 50, 36)
    mast_font = fonts.get("serif_bold", mast_size)
    bx0, by0, bx1, by1 = mast_font.getbbox(masthead_title, anchor="ls")
    glyph_h = by1 - by0
    band_mid_y = (upper_rule_y + 1 + nameplate_bottom_rule - 1) / 2.0
    baseline_mast_y = round(band_mid_y + glyph_h / 2.0 - by1)
    mast_w = bx1 - bx0
    draw.text(
        (round(left_x + (content_w - mast_w) / 2.0 - bx0), baseline_mast_y),
        masthead_title,
        font=mast_font,
        fill=INK,
        anchor="ls",
    )

    draw.line(
        [(left_x, nameplate_bottom_rule), (right_x, nameplate_bottom_rule)],
        fill=HAIRLINE_DARK,
        width=1,
    )

    # Prominent date bar: date left-aligned, tagline right-aligned
    date_bar_top = nameplate_bottom_rule + 3  # 82
    date_text = data["date_line"]
    tagline_text = "One image, the whole day"
    draw.rectangle([left_x, date_bar_top + 4, left_x + 5, date_bar_top + 18], fill=RED)
    draw_text_line(draw, left_x + 12, date_bar_top, date_text, fonts, "sans_bold", 17, INK)

    tag_w = measure_text(draw, tagline_text, fonts, "sans_italic", 15)
    draw_text_line(draw, right_x - tag_w, date_bar_top + 2, tagline_text, fonts, "sans_italic", 15, INK)

    date_rule_red_y = date_bar_top + 23  # 105
    draw.rectangle([left_x, date_rule_red_y, right_x, date_rule_red_y + 1], fill=RED)
    mast_bottom_y = date_rule_red_y + 4  # 109
    draw.line([(left_x, mast_bottom_y), (right_x, mast_bottom_y)], fill=HAIRLINE_DARK, width=1)

    # =========================================================================
    # 2. HERO WOODCUT BAND (y = 115 .. 359, height = 244 px, full width)
    # =========================================================================
    hero_top = mast_bottom_y + 6  # 115
    hero_h = 244
    hero_banner = prepare_hero_banner(hero_path, content_w, hero_h)
    img.paste(hero_banner, (left_x, hero_top))
    draw.rectangle(
        [left_x, hero_top, right_x - 1, hero_top + hero_h - 1],
        outline=HAIRLINE_DARK,
        width=1,
    )
    hero_bottom = hero_top + hero_h  # 359

    # =========================================================================
    # 3. LEAD STORY (y = 370 .. 463)
    # =========================================================================
    lead = data["lead"]
    ly = hero_bottom + 7  # 370

    lead_hl_size, lead_hl_lines = fit_wrapped_text(
        draw,
        lead["headline"],
        content_w,
        fonts,
        "serif_bold",
        34,
        24,
        max_lines=2,
        balanced=True,
    )
    lead_hl_lh = round(lead_hl_size * 1.16)
    for line in lead_hl_lines:
        draw_text_line(draw, left_x, ly, line, fonts, "serif_bold", lead_hl_size, INK)
        ly += lead_hl_lh
    ly += 4

    lead_sum_size, lead_sum_lines = fit_wrapped_text(
        draw,
        lead["summary"],
        content_w,
        fonts,
        "sans_reg",
        16,
        13,
        max_lines=3,
        balanced=False,
    )
    lead_sum_lh = round(lead_sum_size * 1.28)
    lead_src_str = f"\u2014 {lead['source']}"
    lead_src_size = 14
    lead_src_w = measure_text(draw, lead_src_str, fonts, "sans_italic", lead_src_size)

    for idx, line in enumerate(lead_sum_lines):
        lw = draw_text_line(draw, left_x, ly, line, fonts, "sans_reg", lead_sum_size, INK)
        if idx == len(lead_sum_lines) - 1 and lw + 14 + lead_src_w <= content_w:
            draw_text_line(
                draw,
                left_x + lw + 12,
                ly + 1,
                lead_src_str,
                fonts,
                "sans_italic",
                lead_src_size,
                INK,
            )
            placed_lead_src_inline = True
        else:
            placed_lead_src_inline = False
        ly += lead_sum_lh

    if not placed_lead_src_inline:
        draw_text_line(draw, left_x, ly, lead_src_str, fonts, "sans_italic", lead_src_size, INK)
        ly += round(lead_src_size * 1.25)

    # Double divider rule between Lead Story and 3-Column Story Grid
    grid_rule_y = ly + 5
    draw.line([(left_x, grid_rule_y), (right_x, grid_rule_y)], fill=HAIRLINE_DARK, width=2)
    draw.line([(left_x, grid_rule_y + 3), (right_x, grid_rule_y + 3)], fill=HAIRLINE_MUTED, width=1)

    # =========================================================================
    # 4. THREE-COLUMN STORY GRID (WORLD / BUSINESS / SCIENCE & TECH)
    # =========================================================================
    footer_h = 52
    footer_top = CANVAS_H - MARGIN - footer_h  # 944
    grid_top = grid_rule_y + 9
    grid_bottom = footer_top - 10  # 934 (clean 10 px breathing margin above footer)
    grid_avail_h = grid_bottom - grid_top

    # Proportional column widths tailored to story density (314 + 20 + 264 + 20 + 350 = 968)
    col_gap = 20
    col_widths = [314, 264, 350]
    col_xs = [
        left_x,
        left_x + col_widths[0] + col_gap,
        left_x + col_widths[0] + col_gap + col_widths[1] + col_gap,
    ]

    for div_idx in (1, 2):
        vx = col_xs[div_idx] - col_gap // 2
        draw.line([(vx, grid_top), (vx, grid_bottom)], fill=HAIRLINE_MUTED, width=1)

    grouped_stories: list[tuple[str, list[dict[str, str]]]] = []
    for sec_name in SECTION_GROUPS:
        sec_items = [st for st in data["stories"] if st["section"] == sec_name]
        grouped_stories.append((sec_name, sec_items))

    def layout_grid_story(
        story: dict[str, str],
        width: float,
        max_hl_size: int,
        sum_size: int,
        boxed: bool = False,
    ) -> dict:
        inner_w = width - 20 if boxed else width
        h_size, h_lines = fit_wrapped_text(
            draw,
            story["headline"],
            inner_w,
            fonts,
            "serif_bold",
            max_hl_size,
            14,
            max_lines=2,
            balanced=True,
        )
        h_lh = round(h_size * 1.15)
        s_lines = wrap_words(draw, story["summary"], inner_w, fonts, "sans_reg", sum_size, balanced=False)
        s_lh = round(sum_size * 1.24)

        src_str = f"\u2014 {story['source']}"
        src_size = 12
        src_w = measure_text(draw, src_str, fonts, "sans_italic", src_size)
        last_line_w = measure_text(draw, s_lines[-1], fonts, "sans_reg", sum_size)
        inline_src = (not boxed) and (last_line_w + 8 + src_w <= inner_w)
        src_extra_h = 0 if inline_src else (src_size + 3)
        pad_v = 18 if boxed else 0
        height = pad_v + len(h_lines) * h_lh + 3 + len(s_lines) * s_lh + src_extra_h
        return {
            "h_size": h_size,
            "h_lines": h_lines,
            "h_lh": h_lh,
            "s_size": sum_size,
            "s_lines": s_lines,
            "s_lh": s_lh,
            "src_str": src_str,
            "src_size": src_size,
            "inline_src": inline_src,
            "boxed": boxed,
            "height": height,
        }

    # Verify 13 px summary fits comfortably; keep >= 13 px per spec
    sum_font_size = 13
    header_band_h = 22

    # First measure columns 0 and 2 (4 stories each) to establish target bottom alignment
    col_layouts: list[list[dict]] = []
    for c_idx, (_, sec_items) in enumerate(grouped_stories):
        cw = col_widths[c_idx]
        max_hl = 18 if c_idx == 1 else 17
        cards = [
            layout_grid_story(
                st,
                cw,
                max_hl_size=max_hl,
                sum_size=sum_font_size,
                boxed=(c_idx == 1 and s_i == len(sec_items) - 1),
            )
            for s_i, st in enumerate(sec_items)
        ]
        col_layouts.append(cards)

    # Compute exact gap arrays for columns 0 and 2 so all three columns end flush at target_grid_bottom
    natural_bottoms: dict[int, int] = {}
    for c_idx in (0, 2):
        cards = col_layouts[c_idx]
        used_h = header_band_h + sum(c["height"] for c in cards)
        min_gap_total = 16 * (len(cards) - 1)
        natural_bottoms[c_idx] = grid_top + used_h + min_gap_total

    target_grid_bottom = min(grid_bottom, max(natural_bottoms[0], natural_bottoms[2]) + 4)

    for c_idx, (sec_name, _) in enumerate(grouped_stories):
        cx = col_xs[c_idx]
        cw = col_widths[c_idx]
        cards = col_layouts[c_idx]

        # Section header at group top in accent red uppercase
        cy = grid_top
        draw.rectangle([cx, cy + 3, cx + 4, cy + 14], fill=RED)
        draw_text_line(draw, cx + 9, cy, sec_name, fonts, "sans_bold", 13, RED)
        sec_rule_y = cy + 17
        draw.line([(cx, sec_rule_y), (cx + cw, sec_rule_y)], fill=RED, width=1)
        cy = grid_top + header_band_h

        if c_idx in (0, 2):
            used_h = header_band_h + sum(c["height"] for c in cards)
            total_gap_px = max((len(cards) - 1) * 12, target_grid_bottom - grid_top - used_h)
            n_gaps = len(cards) - 1
            base_gap, rem_gap = divmod(total_gap_px, n_gaps)
            gap_list = [base_gap + (1 if g_i < rem_gap else 0) for g_i in range(n_gaps)]

            for idx, card in enumerate(cards):
                for hline in card["h_lines"]:
                    draw_text_line(draw, cx, cy, hline, fonts, "serif_bold", card["h_size"], INK)
                    cy += card["h_lh"]
                cy += 3
                for s_i, sline in enumerate(card["s_lines"]):
                    lw = draw_text_line(draw, cx, cy, sline, fonts, "sans_reg", card["s_size"], INK)
                    if s_i == len(card["s_lines"]) - 1 and card["inline_src"]:
                        draw_text_line(
                            draw,
                            cx + lw + 7,
                            cy + 1,
                            card["src_str"],
                            fonts,
                            "sans_italic",
                            card["src_size"],
                            INK,
                        )
                    cy += card["s_lh"]
                if not card["inline_src"]:
                    draw_text_line(
                        draw, cx, cy, card["src_str"], fonts, "sans_italic", card["src_size"], INK
                    )
                    cy += card["src_size"] + 3

                if idx < len(cards) - 1:
                    g_px = gap_list[idx]
                    rule_y = cy + g_px // 2
                    draw.line([(cx, rule_y), (cx + cw, rule_y)], fill=HAIRLINE_MUTED, width=1)
                    cy += g_px
        else:
            # Middle column (BUSINESS, 3 stories): equal gaps above boxed 3rd brief, bottom-aligned
            box_card = cards[-1]
            box_bot = target_grid_bottom
            box_top = box_bot - box_card["height"]
            top_cards = cards[:-1]
            avail_above_box = box_top - cy
            top_cards_h = sum(c["height"] for c in top_cards)
            mid_gap = max(14, (avail_above_box - top_cards_h) // len(top_cards))

            for idx, card in enumerate(top_cards):
                for hline in card["h_lines"]:
                    draw_text_line(draw, cx, cy, hline, fonts, "serif_bold", card["h_size"], INK)
                    cy += card["h_lh"]
                cy += 3
                for s_i, sline in enumerate(card["s_lines"]):
                    lw = draw_text_line(draw, cx, cy, sline, fonts, "sans_reg", card["s_size"], INK)
                    if s_i == len(card["s_lines"]) - 1 and card["inline_src"]:
                        draw_text_line(
                            draw,
                            cx + lw + 7,
                            cy + 1,
                            card["src_str"],
                            fonts,
                            "sans_italic",
                            card["src_size"],
                            INK,
                        )
                    cy += card["s_lh"]
                if not card["inline_src"]:
                    draw_text_line(
                        draw, cx, cy, card["src_str"], fonts, "sans_italic", card["src_size"], INK
                    )
                    cy += card["src_size"] + 3

                if idx < len(top_cards) - 1:
                    rule_y = cy + mid_gap // 2
                    draw.line([(cx, rule_y), (cx + cw, rule_y)], fill=HAIRLINE_MUTED, width=1)
                    cy += mid_gap

            # Render boxed 3rd BUSINESS brief anchored flush with bottom of outer columns
            box_top = max(cy + 10, box_top)
            box_bot = box_top + box_card["height"]
            draw.rectangle([cx, box_top, cx + cw, box_bot], outline=HAIRLINE_MUTED, width=1)
            draw.rectangle([cx, box_top, cx + cw, box_top + 2], fill=RED)
            tx = cx + 10
            ty = box_top + 9
            for hline in box_card["h_lines"]:
                draw_text_line(draw, tx, ty, hline, fonts, "serif_bold", box_card["h_size"], INK)
                ty += box_card["h_lh"]
            ty += 3
            for sline in box_card["s_lines"]:
                draw_text_line(draw, tx, ty, sline, fonts, "sans_reg", box_card["s_size"], INK)
                ty += box_card["s_lh"]
            draw_text_line(
                draw, tx, ty, box_card["src_str"], fonts, "sans_italic", box_card["src_size"], INK
            )

    # =========================================================================
    # 5. FOOTER BAND: ON THIS DAY (y = 944 .. 996, <= 1.5 lines)
    # =========================================================================
    otd = data["on_this_day"]
    footer_bottom = CANVAS_H - MARGIN  # 996
    draw.rectangle([left_x, footer_top, right_x, footer_bottom], outline=HAIRLINE_DARK, width=1)
    draw.rectangle([left_x, footer_top, left_x + 5, footer_bottom], fill=RED)

    otd_prefix = f"On this day \u00b7 {otd['year']}"
    otd_sep = "  \u2014  "
    otd_text = otd["text"]
    in_x = left_x + 15
    in_w = content_w - 28

    otd_size = 14
    for cand_sz in (14, 13, 12):
        pw = measure_text(draw, otd_prefix, fonts, "sans_bold", cand_sz)
        sw = measure_text(draw, otd_sep, fonts, "sans_reg", cand_sz)
        words = otd_text.split()
        line1_words = [words[0]]
        idx_w = 1
        while idx_w < len(words):
            cand_l1 = " ".join(line1_words + [words[idx_w]])
            if pw + sw + measure_text(draw, cand_l1, fonts, "sans_reg", cand_sz) <= in_w:
                line1_words.append(words[idx_w])
                idx_w += 1
            else:
                break
        rem_text = " ".join(words[idx_w:])
        rem_lines = wrap_words(draw, rem_text, in_w, fonts, "sans_reg", cand_sz) if rem_text else []
        if len(rem_lines) <= 1 and (
            not rem_lines or measure_text(draw, rem_lines[0], fonts, "sans_reg", cand_sz) <= in_w * 0.62
        ):
            otd_size = cand_sz
            break

    pw = measure_text(draw, otd_prefix, fonts, "sans_bold", otd_size)
    sw = measure_text(draw, otd_sep, fonts, "sans_reg", otd_size)
    words = otd_text.split()
    line1_words = [words[0]]
    idx_w = 1
    while idx_w < len(words):
        cand_l1 = " ".join(line1_words + [words[idx_w]])
        if pw + sw + measure_text(draw, cand_l1, fonts, "sans_reg", otd_size) <= in_w:
            line1_words.append(words[idx_w])
            idx_w += 1
        else:
            break
    line1_body = " ".join(line1_words)
    line2_body = " ".join(words[idx_w:])

    otd_lh = round(otd_size * 1.30)
    total_otd_h = otd_lh * (2 if line2_body else 1)
    oy = footer_top + (footer_h - total_otd_h) // 2 - 1

    draw_text_line(draw, in_x, oy, otd_prefix, fonts, "sans_bold", otd_size, RED)
    draw_text_line(draw, in_x + pw, oy, otd_sep + line1_body, fonts, "sans_reg", otd_size, INK)
    if line2_body:
        draw_text_line(draw, in_x, oy + otd_lh, line2_body, fonts, "sans_reg", otd_size, INK)

    # Encode deterministic PNG <= 1 MiB
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=9)
    png_bytes = buf.getvalue()
    if len(png_bytes) > MAX_BYTES:
        for colors in (256, 192, 128, 96, 64):
            quantized = img.quantize(
                colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
            )
            buf = io.BytesIO()
            quantized.save(buf, format="PNG", optimize=True, compress_level=9)
            png_bytes = buf.getvalue()
            if len(png_bytes) <= MAX_BYTES:
                break
    return png_bytes


def resolve_output_path() -> Path:
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or os.environ.get("OUTPUT_DIR") or "/output"
    return Path(out_dir) / "entry.png"


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    out_path = resolve_output_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(out_path.parent, 0o755)
    except OSError:
        pass

    if HAS_PIL:
        png_bytes = render_front_page(base_dir)
        out_path.write_bytes(png_bytes)
    else:
        fallback_png = base_dir / "entry.png"
        if fallback_png.resolve() != out_path.resolve():
            shutil.copyfile(fallback_png, out_path)

    try:
        os.chmod(out_path, 0o644)
    except OSError:
        pass


if __name__ == "__main__":
    main()
