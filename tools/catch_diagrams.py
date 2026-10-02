#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Draw the catch-system explainer images for docs/CATCH_AND_SPEAKING.md from the real UI assets.

  uv run tools/catch_diagrams.py   ->  docs/img/catch/pips_by_rarity.png, docs/img/catch/catch_flow.png
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/img/catch"
UI = ROOT / "assets/ui/catch"
PAPER, INK, MUTED, LINE = (255, 248, 230), (90, 58, 40), (140, 112, 92), (215, 190, 150)
FONT = "C:/Windows/Fonts/malgun.ttf"
BOLD = "C:/Windows/Fonts/malgunbd.ttf"


def font(size, bold=False):
    try:
        return ImageFont.truetype(BOLD if bold else FONT, size)
    except OSError:
        return ImageFont.load_default()


def icon(path, size):
    im = Image.open(path).convert("RGBA")
    im.thumbnail((size, size), Image.LANCZOS)
    return im


def paste_center(canvas, im, cx, cy):
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def pips_by_rarity():
    rows = [  # label, insects, pip, count, notes
        ("1등급 · 흔함", ["butterfly", "bee", "grasshopper", "cricket"], "pip_green", 3,
         "기회 3번 · 초록 구간 넓음 · 찬스는 단어 한 개"),
        ("2등급 · 가끔", ["rhino_beetle", "stag_beetle", "firefly"], "pip_blue", 3,
         "기회 3번 · 마커가 빠름 · 찬스는 단어 한 개"),
        ("3등급 · 희귀", ["jewel_beetle"], "pip_gold", 2,
         "기회 2번 · 초록 구간 좁음 · 찬스는 짧은 문장"),
    ]
    W, rowh, top = 1200, 190, 110
    im = Image.new("RGBA", (W, top + rowh * len(rows) + 150), PAPER + (255,))
    d = ImageDraw.Draw(im)
    d.text((40, 32), "곤충 등급별 남은 기회 (동그라미 표시)", font=font(40, True), fill=INK)
    for i, (label, bugs, pip, count, note) in enumerate(rows):
        y = top + i * rowh
        d.rounded_rectangle((24, y + 8, W - 24, y + rowh - 8), 22, fill=(255, 253, 244), outline=LINE, width=3)
        d.text((52, y + 30), label, font=font(30, True), fill=INK)
        d.text((52, y + 128), note, font=font(24), fill=MUTED)
        for j, bug in enumerate(bugs):
            paste_center(im, icon(ROOT / f"assets/insects/icons/{bug}.png", 78), 330 + j * 86, y + 70)
        for k in range(count):
            paste_center(im, icon(UI / f"{pip}.png", 86), 760 + k * 100, y + 82)
    y = top + rowh * len(rows) + 10
    d.text((52, y + 10), "튼튼한 채집망(2단계)을 끼면 모든 등급에 +1", font=font(28, True), fill=INK)
    paste_center(im, icon(ROOT / "assets/items/gear/net_sturdy.png", 80), 760, y + 62)
    d.text((812, y + 40), "+1", font=font(40, True), fill=(110, 160, 80))
    paste_center(im, icon(UI / "pip_green.png", 80), 920, y + 62)
    d.text((52, y + 70), "한 번 놓칠 때마다 동그라미가 회색으로 바뀐다 →", font=font(24), fill=MUTED)
    paste_center(im, icon(UI / "pip_empty.png", 70), 1110, y + 62)
    im.convert("RGB").save(OUT / "pips_by_rarity.png", optimize=True)


def catch_flow():
    steps = [  # icon(s), title, body
        (["gauge_track"], "1. 게이지 바", "곤충에 다가가 탭하면 머리 위에 게이지가 뜬다. 마커가 초록 구간에 왔을 때 탭!"),
        (["pip_green", "pip_green", "pip_empty"], "2. 놓치면 동그라미 하나가 회색", "곤충이 휙 피한다. 따라가서 다시 시도. 남은 동그라미 = 남은 기회"),
        (["pip_empty", "pip_empty", "pip_empty"], "3. 동그라미를 다 쓰면 도망 직전", "곤충이 날개를 들고 '!'가 뜬다. 5초 동안 찬스 버튼이 나온다"),
        (["chance_button"], "4. 찬스 버튼 → 영어로 말하기", "곤충 이름을 말한다: \"butterfly!\" (3등급은 \"It's a jewel beetle!\")"),
        (["mic_listening"], "5. 기기 안에서 음성 인식", "발음이 통과하면 곤충이 멈칫 → 넓은 초록 구간으로 마지막 한 번"),
        (["check", "oops"], "6. 성공하면 도감 등록, 실패하면 도망", "도망가도 도감에 실루엣과 단어 소리가 남는다 (벌점 없음)"),
    ]
    W, h = 900, 150
    im = Image.new("RGBA", (W, 90 + h * len(steps)), PAPER + (255,))
    d = ImageDraw.Draw(im)
    d.text((32, 24), "채집 흐름과 찬스 버튼", font=font(36, True), fill=INK)
    for i, (icons, title, body) in enumerate(steps):
        y = 90 + i * h
        d.rounded_rectangle((20, y + 6, W - 20, y + h - 10), 20, fill=(255, 253, 244), outline=LINE, width=3)
        for j, name in enumerate(icons):
            size = {"gauge_track": 170, "chance_button": 170, "mic_listening": 108}.get(name, 62)
            paste_center(im, icon(UI / f"{name}.png", size), 125 + (j - (len(icons) - 1) / 2) * 70, y + h / 2 - 2)
        d.text((240, y + 22), title, font=font(28, True), fill=INK)
        words, line, lines = body.split(" "), "", []
        for w in words:  # naive wrap at ~30 chars
            if len(line) + len(w) > 32:
                lines.append(line); line = w
            else:
                line = (line + " " + w).strip()
        lines.append(line)
        for k, text in enumerate(lines[:2]):
            d.text((240, y + 64 + k * 32), text, font=font(22), fill=MUTED)
        if i < len(steps) - 1:
            d.polygon([(120, y + h - 4), (108, y + h - 18), (132, y + h - 18)], fill=LINE)
    im.convert("RGB").save(OUT / "catch_flow.png", optimize=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    pips_by_rarity()
    catch_flow()
    print("wrote", OUT / "pips_by_rarity.png", OUT / "catch_flow.png")
