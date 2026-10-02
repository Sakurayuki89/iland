#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Draw the weather/time explainer images for docs/WEATHER_AND_SPAWN.md from the real map and assets.

  uv run tools/weather_diagrams.py   ->  docs/img/weather/local_weather_map.png, docs/img/weather/island_clock.png
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/img/weather"
PAPER, INK, MUTED, LINE = (255, 248, 230), (90, 58, 40), (140, 112, 92), (215, 190, 150)
FONT, BOLD = "C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/malgunbd.ttf"


def font(size, bold=False):
    try:
        return ImageFont.truetype(BOLD if bold else FONT, size)
    except OSError:
        return ImageFont.load_default()


def icon(rel, size):
    im = Image.open(ROOT / rel).convert("RGBA")
    im.thumbnail((size, size), Image.LANCZOS)
    return im


def put(canvas, rel, size, cx, cy):
    im = icon(rel, size)
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def label(d, xy, text, size=26, fill=INK, bg=(255, 250, 238, 230)):
    f = font(size, True)
    x, y = xy
    l, t, r, b = d.textbbox((x, y), text, font=f)
    d.rounded_rectangle((l - 10, t - 6, r + 10, b + 6), 12, fill=bg, outline=LINE, width=2)
    d.text((x, y), text, font=f, fill=fill)


def weather_map():
    W, H, cw, ch = 1600, 900, 400, 225
    base = Image.open(ROOT / "docs/img/island_overview.png").convert("RGBA").resize((W, H), Image.LANCZOS)
    im = Image.new("RGBA", (W, H + 190), PAPER + (255,))
    im.alpha_composite(base, (0, 0))
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    o = ImageDraw.Draw(over)
    # rain cloud over rows 0-1, cols 0-1
    o.rounded_rectangle((8, 8, 2 * cw - 8, 2 * ch - 8), 40, fill=(70, 95, 140, 85), outline=(60, 90, 150, 220), width=6)
    for x in range(-200, 2 * cw, 34):  # rain streaks
        for y in range(20, 2 * ch - 20, 70):
            o.line((x + y * 0.35, y, x + y * 0.35 + 10, y + 26), fill=(225, 240, 255, 170), width=3)
    # windy zones: hill + coast; calm forest
    for r, c in ((0, 2), (3, 0), (3, 1), (3, 2), (3, 3)):
        x0, y0 = c * cw, r * ch
        for k in range(3):
            yy = y0 + 60 + k * 45
            o.arc((x0 + 40 + k * 30, yy - 30, x0 + 300 + k * 30, yy + 30), 200, 340, fill=(255, 255, 255, 210), width=5)
    for r, c in ((0, 3), (1, 3), (2, 3)):
        o.rectangle((c * cw + 6, r * ch + 6, (c + 1) * cw - 6, (r + 1) * ch - 6), outline=(70, 130, 70, 200), width=4)
    im.alpha_composite(over, (0, 0))
    d = ImageDraw.Draw(im)
    put(im, "assets/fx/weather/rain_cloud.png", 190, cw, ch - 30)
    put(im, "assets/insects/icons/worm.png", 120, cw - 170, ch + 110)
    put(im, "assets/insects/icons/snail.png", 120, cw + 170, ch + 110)
    label(d, (cw - 150, 28), "비구름 (2×2 구역)", 30)
    # movement arrow toward the east
    ax, ay = 2 * cw - 20, ch
    d.line((ax, ay, ax + 230, ay), fill=(60, 90, 150), width=12)
    d.polygon([(ax + 260, ay), (ax + 222, ay - 30), (ax + 222, ay + 30)], fill=(60, 90, 150))
    label(d, (ax + 10, ay + 34), "바람 따라 이동", 24)
    # lake creatures
    put(im, "assets/insects/icons/water_beetle.png", 110, 2 * cw + 140, 2 * ch + 120)
    put(im, "assets/insects/icons/water_strider.png", 110, 2 * cw + 270, 2 * ch + 120)
    label(d, (2 * cw + 60, 2 * ch + 20), "호수: 물방개·소금쟁이", 24)
    label(d, (2 * cw + 60, 3 * ch + 150), "해안: 바람 셈", 24)
    label(d, (3 * cw + 60, ch + 20), "숲: 바람 약함", 24)
    label(d, (2 * cw + 70, 40), "언덕: 바람 셈 · 맑은 낮 비단벌레", 22)
    put(im, "assets/words/sun.png", 110, 2 * cw + cw / 2, ch + ch / 2 + 10)
    # legend
    y = H + 22
    d.text((30, y), "섬 일부에만 오는 비와 바람", font=font(34, True), fill=INK)
    d.text((30, y + 58), "비 오는 구역: 지렁이·달팽이가 나오고, 나비·꿀벌·메뚜기는 잎 아래로 숨는다. 장화를 신으면 진흙에서 느려지지 않는다.", font=font(23), fill=MUTED)
    d.text((30, y + 96), "비 확률 30% · 3일 동안 비가 없으면 다음 날은 반드시 비 · 지나간 구역은 2분 동안 \"비 갠 뒤\"(나비 +50%, 가끔 무지개).", font=font(23), fill=MUTED)
    d.text((30, y + 134), "바람 세기 2: 게이지 초록 구간이 좌우로 흔들린다(날개 운동화는 절반).", font=font(23), fill=MUTED)
    im.convert("RGB").save(OUT / "local_weather_map.png", optimize=True)


def island_clock():
    S, cx, cy, R, w = 1000, 500, 470, 330, 110
    im = Image.new("RGBA", (S, 880), PAPER + (255,))
    d = ImageDraw.Draw(im)
    phases = [  # name, minutes, colour, icons
        ("아침 4분", 4, (250, 222, 140), ["butterfly", "bee"]),
        ("낮 7분", 7, (170, 215, 140), ["grasshopper", "dragonfly", "jewel_beetle", "water_strider"]),
        ("노을 3분", 3, (240, 165, 110), ["dragonfly", "cricket"]),
        ("밤 6분", 6, (80, 95, 150), ["rhino_beetle", "firefly", "moth", "water_beetle"]),
    ]
    start = -90.0
    for name, minutes, colour, bugs in phases:
        sweep = 360 * minutes / 20
        d.pieslice((cx - R, cy - R, cx + R, cy + R), start, start + sweep, fill=colour, outline=PAPER, width=6)
        mid = math.radians(start + sweep / 2)
        lx, ly = cx + math.cos(mid) * (R + 70), cy + math.sin(mid) * (R + 70)
        f = font(30, True)
        tw = d.textlength(name, font=f)
        d.text((lx - tw / 2, ly - 18), name, font=f, fill=INK)
        n = len(bugs)
        for i, bug in enumerate(bugs):
            a = math.radians(start + sweep * (i + 1) / (n + 1))
            put(im, f"assets/insects/icons/{bug}.png", 74, cx + math.cos(a) * (R - w / 2), cy + math.sin(a) * (R - w / 2))
        start += sweep
    d.ellipse((cx - R + w, cy - R + w, cx + R - w, cy + R - w), fill=(255, 252, 242), outline=LINE, width=4)
    put(im, "assets/ui/hud/clock_day.png", 120, cx - 66, cy - 60)
    put(im, "assets/ui/hud/clock_night.png", 120, cx + 66, cy - 60)
    for i, (text, size, fill) in enumerate((("섬 시계 20분 = 하루", 32, INK), ("한 번 놀면 낮과 밤을 모두 본다", 21, MUTED), ("식물은 실제 시간으로 자란다", 21, MUTED))):
        f = font(size, i == 0)
        tw = d.textlength(text, font=f)
        d.text((cx - tw / 2, cy + 14 + i * 44 + (10 if i else 0)), text, font=f, fill=fill)
    im.convert("RGB").save(OUT / "island_clock.png", optimize=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    weather_map()
    island_clock()
    print("wrote", OUT / "local_weather_map.png", OUT / "island_clock.png")
