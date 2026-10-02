#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Draw the island layout + scale review images used by docs/ISLAND_LAYOUT.md.

  uv run tools/island_overview.py

  docs/img/island_overview.png  AI overview map stretched to the world (GRID x GRID screens), zone grid,
                                one screen and the cat at true world size
  docs/img/scale_chart.png      cat vs insects / props / buildings / trees on the 48 px tile grid
Run tools/env_slicer.py first (uses assets/env and assets/insects/icons).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from _common import utf8_output

ROOT = Path(__file__).resolve().parent.parent
MAP = "content/island_overview_2fdd3fe2.png"
SCREEN = (960, 540)  # logical game canvas (apps/client/src/main.ts)
GRID = 4  # zones per side, one screen each
WORLD = (SCREEN[0] * GRID, SCREEN[1] * GRID)
TILE = 48
SRC = 2  # stored px per world px
WALK = 140  # px/s

# insects in the world are drawn bigger than life so kids can tap them (cat head ~ 45 px)
INSECT_WORLD = {"butterfly": 40, "bee": 28, "dragonfly": 48, "grasshopper": 34, "rhino_beetle": 38,
                "stag_beetle": 40, "firefly": 24, "cricket": 32, "moth": 40, "jewel_beetle": 30}


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for name in (["malgunbd.ttf"] if bold else []) + ["malgun.ttf", "AppleSDGothicNeo.ttc", "NotoSansCJK-Regular.ttc"]:
        for d in (Path("C:/Windows/Fonts"), Path("/System/Library/Fonts"), Path("/usr/share/fonts/opentype/noto")):
            if (d / name).exists():
                return ImageFont.truetype(str(d / name), size)
    return ImageFont.load_default()


def cat_frame() -> Image.Image:
    """down_idle of cat_base at stored (2x) size."""
    atlas = json.loads((ROOT / "assets/sprites/cat_base.json").read_text(encoding="utf-8"))
    f = atlas["frames"]["down_idle"]["frame"]
    return Image.open(ROOT / "assets/sprites/cat_base.png").convert("RGBA").crop(
        (f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"]))


def at_world(img: Image.Image, k: float = 1.0) -> Image.Image:
    """Stored 2x asset -> world px (times k for a zoomed chart)."""
    return img.resize((max(1, round(img.width / SRC * k)), max(1, round(img.height / SRC * k))), Image.LANCZOS)


def label(d: ImageDraw.ImageDraw, xy, text, size, fill=(255, 255, 255, 255), anchor="mm"):
    d.text(xy, text, font=font(size, True), fill=fill, anchor=anchor, stroke_width=max(2, size // 8),
           stroke_fill=(70, 45, 30, 255))


def overview(cat: Image.Image) -> None:
    W, H = WORLD
    img = Image.open(ROOT / MAP).convert("RGBA").resize((W, H), Image.LANCZOS)
    over = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(over)
    sw, sh = SCREEN
    zones = json.loads((ROOT / "data/world/zones.json").read_text(encoding="utf-8"))
    start = next(zone for zone in zones if zone["name_en"] == "Camp")
    for zone in zones:
        r, c = zone["row"], zone["col"]
        name = zone["name_ko"] + (" (후속)" if zone["status"] == "later" else "")
        d.rectangle((c * sw, r * sh, (c + 1) * sw - 1, (r + 1) * sh - 1), outline=(255, 255, 255, 170), width=3)
        label(d, (c * sw + 18, r * sh + 14), name, 34, anchor="la")
    # one screen around the camp, and the cat at true world size inside it
    x0, y0 = start["col"] * sw, start["row"] * sh
    d.rectangle((x0, y0, x0 + sw - 1, y0 + sh - 1), outline=(255, 90, 60, 255), width=8)
    label(d, (x0 + sw - 18, y0 + sh - 14), f"화면 1장 = {sw}×{sh} (타일 {sw // TILE}×{sh / TILE:g})", 26,
          fill=(255, 230, 220, 255), anchor="rd")
    c1 = at_world(cat)
    cx, cy = x0 + sw // 2 - 150, y0 + sh // 2 + 120
    over.alpha_composite(c1, (cx - c1.width // 2, cy - c1.height))
    label(d, (cx, cy + 6), f"고양이 {c1.height}px", 22, anchor="ma")
    # tile grid on a 4x3 patch next to the cat
    gx, gy = cx + 70, cy - 3 * TILE
    for k in range(5):
        d.line((gx + k * TILE, gy, gx + k * TILE, gy + 3 * TILE), fill=(255, 255, 255, 200), width=2)
    for k in range(4):
        d.line((gx, gy + k * TILE, gx + 4 * TILE, gy + k * TILE), fill=(255, 255, 255, 200), width=2)
    label(d, (gx + 2 * TILE, gy - 8), f"타일 {TILE}px", 22, anchor="md")
    label(d, (W // 2, H - 24), f"섬 월드 {W}×{H}px = 화면 {GRID}×{GRID} = 타일 {W // TILE}×{H // TILE}  ·  "
          f"걷기 {WALK}px/s → 화면 1장 약 {sw / WALK:.0f}초, 섬 가로 약 {W / WALK:.0f}초, 세로 약 {H / WALK:.0f}초  ·  "
          "지도 그림은 배치 참고용(소품 크기는 실제 비율 아님)", 26, anchor="md")
    img.alpha_composite(over)
    out = ROOT / "docs/img/island_overview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out)
    print(f"wrote {out.relative_to(ROOT)} ({W}x{H})")


def scale_chart(cat: Image.Image) -> None:
    k = 2  # chart zoom: draw world px at 2x so small things stay readable
    manifest = json.loads((ROOT / "assets/env/manifest.json").read_text(encoding="utf-8"))
    env = ["flowers/tulip", "flowers/sunflower", "plants/bush", "props/barrel", "props/bench",
           "props/bulletin_board", "props/lantern_post", "buildings/tent", "buildings/cabin",
           "trees/oak", "trees/pine", "trees/old_tree"]
    rows = [
        [("고양이", at_world(cat, k))] + [
            (n, Image.open(ROOT / f"assets/insects/icons/{n}.png").convert("RGBA")) for n in INSECT_WORLD],
        [("고양이", at_world(cat, k))] + [
            (key.split("/")[1], at_world(Image.open(ROOT / "assets" / manifest[key]["file"]).convert("RGBA"), k))
            for key in env],
    ]
    # insect icons are a 256 box: shrink the drawing itself to its world width
    fixed = []
    for name, im in rows[0]:
        if name in INSECT_WORLD:
            bb = im.getbbox()
            im = im.crop(bb)
            s = INSECT_WORLD[name] * k / im.width
            im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
        fixed.append((name, im))
    rows[0] = fixed

    g, gap, pad = TILE * k, 44, 60
    heights = [max(im.height for _, im in r) + 90 for r in rows]
    W = max(sum(im.width + gap for _, im in r) for r in rows) + pad * 2
    H = sum(heights) + pad
    sheet = Image.new("RGBA", (W, H), (214, 232, 178, 255))
    d = ImageDraw.Draw(sheet)
    for x in range(0, W, g):
        d.line((x, 0, x, H), fill=(180, 205, 150, 255), width=1)
    for y in range(0, H, g):
        d.line((0, y, W, y), fill=(180, 205, 150, 255), width=1)
    y = pad
    for r, h in zip(rows, heights):
        base = y + h - 60
        d.line((pad // 2, base, W - pad // 2, base), fill=(120, 90, 60, 255), width=2)
        x = pad
        for name, im in r:
            sheet.alpha_composite(im, (x, base - im.height))
            d.text((x + im.width // 2, base + 8), f"{name}\n{round(im.width / k)}×{round(im.height / k)}", font=font(18),
                   fill=(70, 45, 30, 255), anchor="ma", align="center")
            x += im.width + gap
        y += h
    d.text((W - pad, 16), f"모눈 1칸 = 타일 {TILE}px (2배 확대)", font=font(22, True), fill=(70, 45, 30, 255), anchor="ra")
    out = ROOT / "docs/img/scale_chart.png"
    sheet.convert("RGB").save(out)
    print(f"wrote {out.relative_to(ROOT)} ({W}x{H})")


def main() -> int:
    utf8_output()
    cat = cat_frame()
    overview(cat)
    scale_chart(cat)
    return 0


if __name__ == "__main__":
    sys.exit(main())
