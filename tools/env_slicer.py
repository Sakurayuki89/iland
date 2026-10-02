#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy", "scipy"]
# ///
"""Cut the AI environment / insect-icon / terrain sheets in content/ into game-ready PNGs.

  uv run tools/env_slicer.py            # everything
  uv run tools/env_slicer.py trees tiles_grass_water   # selected jobs

Scale rule (docs/ISLAND_LAYOUT.md): files are stored at 2x world size, the game draws them at 0.5.
World sizes below are in world px (cat = 92 px tall, tile = 48 px). Each sheet is cut on an even grid,
so objects must stay inside their own cell; check assets/env/_contact.png after a rebuild.

Outputs
  assets/env/<category>/<name>.png       transparent, trimmed, sized to world*2
  assets/insects/icons/<name>.png        journal / dex icons, 256 px box
  assets/{ui,npc,crops,words,items,fx,fish,wearables}/...   see ICON_SHEETS
  assets/app/icon_1024.png               store icon source
  assets/tiles/ground/<name>.png         seamless ground textures, 384 px (= 4x4 tiles)
  assets/tiles/<set>.png                 3x3 nine-slice tileset for Tiled, 96 px tiles
  assets/env/manifest.json               key -> file, world size, draw scale
  assets/env/_contact.png                review sheet
The original content/*.png files are only read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from _common import utf8_output
from sprite_slicer import remove_background

ROOT = Path(__file__).resolve().parent.parent
SRC = 2  # stored px per world px
TILE = 48  # world px
ICON = 256

# name, world size: ("h", px) = height, ("w", px) = width (flat things read better by width)
PROPS: dict[str, tuple[str, str, list[tuple[str, str, int]]]] = {
    "trees": ("content/env_trees_12e42645.png", "trees", [
        ("oak", "h", 230), ("pine", "h", 260), ("sapling", "h", 70),
        ("apple_tree", "h", 230), ("cherry_tree", "h", 230), ("autumn_tree", "h", 230),
        ("stump", "h", 70), ("log", "w", 120), ("old_tree", "h", 300)]),
    "bushes": ("content/env_bushes_e8e4d86b.png", "plants", [
        ("grass_tuft", "h", 30), ("tall_grass", "h", 55), ("bush", "h", 60),
        ("flower_bush", "h", 65), ("berry_bush", "h", 65), ("clover", "h", 35),
        ("fern", "h", 55), ("reeds", "h", 75), ("sprout", "h", 22)]),
    "flowers": ("content/env_flowers_dfe17778.png", "flowers", [
        ("cosmos", "h", 45), ("lavender", "h", 50), ("daisy", "h", 42),
        ("tulip", "h", 45), ("sunflower", "h", 75), ("hydrangea", "h", 50),
        ("rose", "h", 48), ("marigold", "h", 42), ("wildflowers", "h", 40)]),
    "buildings": ("content/env_buildings_07906417.png", "buildings", [
        ("tent", "h", 170), ("cabin", "h", 230), ("cottage", "h", 250),
        ("treehouse", "h", 300), ("shed", "h", 190), ("research_hut", "h", 260),
        ("market_stall", "h", 170), ("well", "h", 150), ("campfire", "w", 150)]),
    "props": ("content/env_props_0fac428a.png", "props", [
        ("bulletin_board", "h", 110), ("signpost", "h", 110), ("mailbox", "h", 90),
        ("bench", "w", 110), ("fence", "w", 96), ("barrel", "h", 55),
        ("crates", "h", 75), ("garden_plot", "w", 144), ("lantern_post", "h", 130)]),
    "water": ("content/env_water_bea22f81.png", "water", [
        ("pond", "w", 260), ("lake", "w", 520), ("dock", "w", 170),
        ("lily_pads", "w", 100), ("stepping_stones", "w", 120), ("bridge", "w", 200),
        ("mossy_rock", "h", 110), ("rowboat", "w", 150), ("waterfall", "h", 200)]),
}

# icon sheet is 4x4, keep only the chosen species (cell index -> name)
INSECT_ICONS = ("content/insects_sheet_0f6c3638.png", 4, 4, {
    0: "butterfly", 2: "bee", 3: "dragonfly", 4: "grasshopper", 6: "rhino_beetle",
    7: "stag_beetle", 8: "firefly", 12: "cricket", 13: "moth", 14: "jewel_beetle"})

# job -> (sheet, rows, cols, out dir under assets/, box px or None, names row-major)
# box: fit into a square box of that size (icons); None: keep trimmed at source size (UI panels, cards).
# A None name skips the cell; a tuple splits the cell's pieces left to right (e.g. button + pressed button).
ICON_SHEETS: dict[str, tuple[str, int, int, str, int | None, list]] = {
    "ui_hud": ("content/ui_hud_7d0d396b.png", 3, 3, "ui/hud", None, [
        "ring", "ring_needle", "star", "star_empty", "heart", "tap_marker", "clock_day", "clock_night", "round_button"]),
    "ui_panels": ("content/ui_panels_3ca39c83.png", 3, 3, "ui/panels", None, [
        "speech_bubble", "dialog_box", "word_card", "journal", "slot", "slot_locked", "bag_slot", "sign_banner",
        ("button", "button_pressed")]),
    "portraits": ("content/npc_portraits_49181ccf.png", 2, 2, "npc/portraits", 512, [
        "professor", "collector", "fisher", "cook"]),
    "crops": ("content/crops_ae5559d1.png", 4, 5, "crops", 256, [
        f"flower_{c}_{s}" for c in ("pink", "blue", "yellow", "white") for s in range(5)]),
    "words": ("content/words_e318408f.png", 3, 4, "words", 512, [
        "cat", "bug", "butterfly", "flower", "leaf", "seed", "water", "net", "jar", "tent", "tree", "sun"]),
    "words_rain": ("content/words_rain_fbaf29bc.png", 2, 2, "words", 512, [
        "worm", "snail", "water_beetle", "water_strider"]),
    # catch gauge + speaking UI (docs/CATCH_AND_SPEAKING.md)
    "ui_catch": ("content/ui_catch_eeeeabd8.png", 4, 4, "ui/catch", None, [
        "speaker", "speaker_playing", "mic", "mic_listening",
        "chance_button", "pip_green", "pip_blue", "pip_gold",
        "pip_empty", "gauge_track", "gauge_marker", "oops",
        "speech_wave", "check", "retry", "slow"]),
    "tools": ("content/items_tools_0b6ae033.png", 3, 3, "items/tools", 256, [
        "net", "jar", "jar_bug", "watering_can", "seed_packet", "backpack", "fishing_rod", "trowel", "basket"]),
    "gear": ("content/gear_tiers_9c7f90bf.png", 3, 3, "items/gear", 256, [  # rows = kind, cols = tier 1-3
        "gloves_cotton", "gloves_garden", "gloves_star", "shoes_canvas", "boots_rain", "sneakers_wing",
        "net_bamboo", "net_sturdy", "net_rainbow"]),
    "rewards": ("content/rewards_0278f002.png", 3, 3, "items/rewards", 256, [
        "shell_coin", "shell_coins", "sticker_sheet", "gift_box", "stamp_card", "star_medal",
        "treasure_chest", "leaf_badge", "upgrade_ticket"]),
    "fx": ("content/fx_b710d0fd.png", 4, 4, "fx", 128, [
        "sparkle", "star_small", "twinkle", "glow", "leaf", "petal", "dirt", "splash",
        "dust", "smoke", "emote_exclaim", "emote_question", "heart", "note", "sweat", "confetti"]),
    "fish": ("content/fish_f5d344e5.png", 3, 3, "fish/icons", 256, [
        "goldfish", "crucian_carp", "catfish", "sea_bream", "mackerel", "clownfish", "crab", "octopus", "pufferfish"]),
    "food": ("content/food_901a4a0c.png", 4, 4, "items/food", 256, [
        "apple", "blueberries", "carrot", "mushroom", "fish_plate", "fish_soup", "bread", "honey",
        "berry_pie", "stew", "rice_ball", "milk", "cooking_pot", "cutting_board", "fruit_salad", "feast_cake"]),
    "role_cards": ("content/role_cards_454a285d.png", 2, 4, "ui/role_cards", None, [
        "gatherer", "gardener", "fisher", "cook", "explorer", "messenger", "helper", "card_back"]),
    "wearables": ("content/wearables_bd368825.png", 3, 3, "wearables", 256, [
        "straw_hat", "red_cap", "bucket_hat", "flower_crown", "leaf_hat", "acorn_beanie", "backpack", "satchel", "bow"]),
    "decor": ("content/decor_events_fb608994.png", 3, 3, "items/decor", 256, [
        "letter", "bottle_letter", "treasure_map", "parcel", "flower_pot", "stone_stack", "log_stool",
        "string_lights", "wind_chime"]),
    "weather": ("content/weather_night_092d92f1.png", 3, 3, "fx/weather", 256, [
        "raindrop", "puddle", "rain_cloud", "cloud", "light_glow", "lit_window", "moon", "night_star", "rainbow"]),
    "ferry": ("content/ferry_d945096f.png", 1, 1, "env/water", 800, ["ferry"]),  # ~400 world px wide
}

CLEAR_HOLES = {"ui_hud"}  # sheets whose large enclosed pure-white areas are holes, not paint

GROUND = ("content/tiles_ground_b4b282d5.png", [
    "grass", "grass_flowers", "forest_floor", "dirt", "sand", "farm_soil", "cobble", "shallow_water", "sea"])

NINE_SLICE = {  # set name -> source; cut into thirds, row-major: nw n ne / w c e / sw s se
    "tiles_grass_water": "content/tiles_grass_water_f8154c7f.png",
    "tiles_dirt_grass": "content/tiles_dirt_grass_3d7017e6.png",
    "tiles_sand_water": "content/tiles_sand_water_bb3762e0.png",
    # inverse sources (water/grass/water hole inside): their corners are the concave (inner) corner tiles
    "tiles_grass_water_inner": "content/tiles_grass_water_inner_5bd7f18c.png",
    "tiles_dirt_grass_inner": "content/tiles_dirt_grass_inner_03c3799a.png",
    "tiles_sand_water_inner": "content/tiles_sand_water_inner_f0fed2e4.png",
}
APP_ICON = "content/app_icon_1ff05bbc.png"
SLICE_NAMES = ["nw", "n", "ne", "w", "c", "e", "sw", "s", "se"]


def load_rgb(rel: str) -> np.ndarray:
    return np.asarray(Image.open(ROOT / rel).convert("RGB"))


def grid_cells(rgba: np.ndarray, rows: int, cols: int):
    h, w = rgba.shape[:2]
    for r in range(rows):
        for c in range(cols):
            yield rgba[r * h // rows:(r + 1) * h // rows, c * w // cols:(c + 1) * w // cols]


def keep_main(cell: np.ndarray, drop_top_left: bool = False) -> np.ndarray:
    """Drop specks and slivers of neighbouring cells; keep the object (and its nearby loose parts)."""
    fg = cell[..., 3] > 8
    lab, n = ndimage.label(ndimage.binary_dilation(fg, iterations=6))
    if n <= 1 and not drop_top_left:
        return cell
    h, w = fg.shape
    areas = ndimage.sum(fg, lab, index=np.arange(1, n + 1))
    biggest = areas.max()
    keep = np.zeros(n + 1, dtype=bool)
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        a = areas[i - 1]
        edge = sl[0].start == 0 or sl[1].start == 0 or sl[0].stop == h or sl[1].stop == w
        badge = drop_top_left and sl[0].stop < h * 0.3 and sl[1].stop < w * 0.3
        keep[i] = a >= 0.02 * biggest and not (edge and a < 0.15 * biggest) and not badge
    out = cell.copy()
    out[~keep[lab]] = 0
    return out


def trim(cell: np.ndarray) -> np.ndarray | None:
    ys, xs = np.nonzero(cell[..., 3] > 8)
    if not len(ys):
        return None
    return cell[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def fit(img: Image.Image, axis: str, world: int) -> Image.Image:
    w, h = img.size
    k = world * SRC / (h if axis == "h" else w)
    return img.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)


def seamless(img: Image.Image) -> Image.Image:
    """Offset-and-blend: the result wraps on both axes."""
    a = np.asarray(img).astype(np.float32)
    n = a.shape[0]
    s = np.roll(a, (n // 2, n // 2), axis=(0, 1))
    t = np.linspace(-1, 1, n)
    d = np.maximum(np.abs(t)[:, None], np.abs(t)[None, :])  # 0 centre .. 1 edge
    wgt = np.clip((0.85 - d) / 0.35, 0, 1)[..., None]
    return Image.fromarray((a * wgt + s * (1 - wgt)).round().astype(np.uint8))


def do_props(job: str, manifest: dict, contact: list) -> None:
    rel, cat, items = PROPS[job]
    rgba = remove_background(load_rgb(rel), tol=14, clear_enclosed=False, min_hole=0)
    out = ROOT / "assets/env" / cat
    out.mkdir(parents=True, exist_ok=True)
    for cell, (name, axis, world) in zip(grid_cells(rgba, 3, 3), items):
        t = trim(keep_main(cell))
        if t is None:
            sys.exit(f"error: {job}/{name} cell is empty")
        img = fit(Image.fromarray(t), axis, world)
        img.save(out / f"{name}.png")
        key = f"{cat}/{name}"
        manifest[key] = {"file": f"env/{cat}/{name}.png", "world": [img.width // SRC, img.height // SRC],
                         "scale": 1 / SRC, "origin": [0.5, 0.95], "source": rel}
        contact.append((key, img))
    print(f"{job}: {len(items)} -> assets/env/{cat}/")


def do_insect_icons(contact: list) -> None:
    rel, rows, cols, keep = INSECT_ICONS
    rgba = remove_background(load_rgb(rel), tol=14, clear_enclosed=False, min_hole=0)
    out = ROOT / "assets/insects/icons"
    out.mkdir(parents=True, exist_ok=True)
    for i, cell in enumerate(grid_cells(rgba, rows, cols)):
        if i not in keep:
            continue
        img = Image.fromarray(trim(keep_main(cell, drop_top_left=True)))  # drop the numbered badge
        img.thumbnail((ICON - 16, ICON - 16), Image.LANCZOS)
        box = Image.new("RGBA", (ICON, ICON))
        box.alpha_composite(img, ((ICON - img.width) // 2, (ICON - img.height) // 2))
        box.save(out / f"{keep[i]}.png")
        contact.append((f"icon/{keep[i]}", box))
    print(f"insect icons: {len(keep)} -> assets/insects/icons/")


def split_pieces(cell: np.ndarray) -> list[np.ndarray]:
    """Separate side-by-side objects in one cell, left to right."""
    lab, n = ndimage.label(ndimage.binary_dilation(cell[..., 3] > 8, iterations=6))
    out = []
    for i, sl in sorted(enumerate(ndimage.find_objects(lab), start=1), key=lambda t: t[1][1].start):
        piece = cell.copy()
        piece[lab != i] = 0
        if (piece[..., 3] > 8).sum() > 0.05 * (cell[..., 3] > 8).sum():
            out.append(trim(piece))
    return out


def do_icons(job: str, contact: list) -> None:
    rel, rows, cols, sub, box, names = ICON_SHEETS[job]
    holes = job in CLEAR_HOLES  # e.g. the inside of the timing ring must be see-through
    rgba = remove_background(load_rgb(rel), tol=14, clear_enclosed=holes, min_hole=5000)
    out = ROOT / "assets" / sub
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for cell, name in zip(grid_cells(rgba, rows, cols), names):
        if name is None:
            continue
        if isinstance(name, tuple):
            pieces = split_pieces(keep_main(cell))
            if len(pieces) != len(name):
                sys.exit(f"error: {job} cell {name} has {len(pieces)} pieces, expected {len(name)}")
        else:
            pieces, name = [trim(keep_main(cell))], (name,)
        for nm, t in zip(name, pieces):
            img = Image.fromarray(t)
            if box:
                img.thumbnail((box - box // 16, box - box // 16), Image.LANCZOS)
                framed = Image.new("RGBA", (box, box))
                framed.alpha_composite(img, ((box - img.width) // 2, (box - img.height) // 2))
                img = framed
            img.save(out / f"{nm}.png")
            contact.append((f"{sub}/{nm}", img))
            n += 1
    print(f"{job}: {n} -> assets/{sub}/")


def do_app_icon(contact: list) -> None:
    out = ROOT / "assets/app"
    out.mkdir(parents=True, exist_ok=True)
    img = Image.open(ROOT / APP_ICON).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    img.save(out / "icon_1024.png")
    contact.append(("app/icon_1024", img))
    print("app icon: assets/app/icon_1024.png (store sizes are generated by the Capacitor asset tool)")


def do_ground(contact: list) -> None:
    rel, names = GROUND
    src = Image.open(ROOT / rel).convert("RGB")
    w, h = src.size
    out = ROOT / "assets/tiles/ground"
    out.mkdir(parents=True, exist_ok=True)
    size = TILE * SRC * 4
    for i, name in enumerate(names):
        r, c = divmod(i, 3)
        x0, y0, x1, y1 = c * w // 3, r * h // 3, (c + 1) * w // 3, (r + 1) * h // 3
        inset = (x1 - x0) // 9  # stay clear of the white gaps and any painted rim
        sw = src.crop((x0 + inset, y0 + inset, x1 - inset, y1 - inset)).resize((size, size), Image.LANCZOS)
        img = seamless(sw)
        img.save(out / f"{name}.png")
        contact.append((f"ground/{name}", img))
    print(f"ground textures: {len(names)} -> assets/tiles/ground/ ({size}px, wraps)")


def do_nine_slice(name: str, contact: list) -> None:
    src = Image.open(ROOT / NINE_SLICE[name]).convert("RGB")
    t = TILE * SRC
    sheet = src.resize((t * 3, t * 3), Image.LANCZOS)
    sheet.save(ROOT / "assets/tiles" / f"{name}.png")
    for i, pos in enumerate(SLICE_NAMES):
        r, c = divmod(i, 3)
        contact.append((f"{name}/{pos}", sheet.crop((c * t, r * t, (c + 1) * t, (r + 1) * t))))
    print(f"{name}: 3x3 tileset ({t}px tiles) -> assets/tiles/{name}.png")


def write_contact(contact: list) -> None:
    cell, cols, pad = 200, 10, 18
    rows = (len(contact) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * (cell + pad)), (205, 225, 170, 255))  # grass-ish, shows halos
    d = ImageDraw.Draw(sheet)
    for i, (label, img) in enumerate(contact):
        r, c = divmod(i, cols)
        im = img.convert("RGBA")
        im.thumbnail((cell - 8, cell - 8), Image.LANCZOS)
        x, y = c * cell, r * (cell + pad)
        sheet.alpha_composite(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
        d.text((x + 4, y + cell), label, fill=(60, 40, 30, 255))
    sheet.save(ROOT / "assets/env/_contact.png")


def main() -> int:
    utf8_output()
    jobs = list(PROPS) + ["insect_icons"] + list(ICON_SHEETS) + ["app_icon", "ground"] + list(NINE_SLICE)
    wanted = sys.argv[1:] or jobs
    unknown = [w for w in wanted if w not in jobs]
    if unknown:
        print(f"unknown job(s): {unknown}. known: {jobs}", file=sys.stderr)
        return 2
    (ROOT / "assets/env").mkdir(parents=True, exist_ok=True)
    mpath = ROOT / "assets/env/manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    contact: list = []
    for job in wanted:
        if job in PROPS:
            do_props(job, manifest, contact)
        elif job == "insect_icons":
            do_insect_icons(contact)
        elif job in ICON_SHEETS:
            do_icons(job, contact)
        elif job == "app_icon":
            do_app_icon(contact)
        elif job == "ground":
            do_ground(contact)
        else:
            do_nine_slice(job, contact)
    mpath.write_text(json.dumps(dict(sorted(manifest.items())), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_contact(contact)
    print("review: assets/env/_contact.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
