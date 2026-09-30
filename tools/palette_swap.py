#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy"]
# ///
"""Recolor the cat atlas into N player looks (spot/tail-tip color + scarf color).

Only two regions are recolored, by soft HSV masks:
  spot  : saturated orange patches / tail tip
  scarf : green neckerchief
Outline (dark brown), cream fur, and pink cheeks are left untouched.

Each palette entry in palettes.json gives target colors; the source reference
colors are measured from the atlas itself, so the shading inside a region is
preserved (relative hue/sat/value mapping).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from _common import utf8_output


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rc = m & (mx == r)
    gc = m & (mx == g) & ~rc
    bc = m & ~rc & ~gc
    h[rc] = ((g - b)[rc] / d[rc]) % 6
    h[gc] = (b - r)[gc] / d[gc] + 2
    h[bc] = (r - g)[bc] / d[bc] + 4
    h = h * 60.0
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    return np.stack([h, s, mx], -1)


def hsv_to_rgb(hsv: np.ndarray) -> np.ndarray:
    h, s, v = hsv[..., 0] % 360.0, hsv[..., 1], hsv[..., 2]
    c = v * s
    x = c * (1 - np.abs((h / 60.0) % 2 - 1))
    m = v - c
    z = np.zeros_like(h)
    seg = (h // 60).astype(int) % 6
    lut = [(c, x, z), (x, c, z), (z, c, x), (z, x, c), (x, z, c), (c, z, x)]
    r = np.choose(seg, [t[0] for t in lut]) + m
    g = np.choose(seg, [t[1] for t in lut]) + m
    b = np.choose(seg, [t[2] for t in lut]) + m
    return np.stack([r, g, b], -1)


def ramp(x, lo, hi):
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def masks(hsv: np.ndarray, alpha: np.ndarray) -> dict[str, np.ndarray]:
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    vis = (alpha > 0.5).astype(np.float32)
    hue_o = ramp(h, 12, 22) * (1 - ramp(h, 46, 56))
    spot = hue_o * ramp(s, 0.30, 0.45) * ramp(v, 0.70, 0.82) * vis
    hue_g = ramp(h, 60, 75) * (1 - ramp(h, 145, 160))
    scarf = hue_g * ramp(s, 0.15, 0.28) * ramp(v, 0.30, 0.42) * vis
    return {"spot": spot, "scarf": scarf}


def ref_color(hsv: np.ndarray, w: np.ndarray) -> np.ndarray:
    sel = w > 0.9
    if not sel.any():
        raise SystemExit("error: mask is empty — is this the expected cat atlas?")
    px = hsv[sel]
    return np.array([np.median(px[:, 0]), np.median(px[:, 1]), np.median(px[:, 2])])


def hex_to_hsv(hx: str) -> np.ndarray:
    hx = hx.lstrip("#")
    rgb = np.array([int(hx[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0
    return rgb_to_hsv(rgb[None, :])[0]


def recolor(hsv, w, ref, target):
    th, ts, tv = target
    rh, rs, rv = ref
    dh = ((hsv[..., 0] - rh + 180) % 360) - 180
    out = np.stack([
        th + dh,
        np.clip(hsv[..., 1] * (ts / max(rs, 1e-3)), 0, 1),
        np.clip(hsv[..., 2] * (tv / max(rv, 1e-3)), 0, 1),
    ], -1)
    return hsv_to_rgb(out), w[..., None]


def main():
    utf8_output()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("atlas", nargs="?", default="assets/sprites/cat_base.png")
    p.add_argument("--palettes", default="data/palettes.json")
    p.add_argument("-o", "--out-dir", default=None, help="default: same folder as the atlas")
    p.add_argument("--prefix", default="cat", help="output stem prefix -> <prefix>_<id>")
    args = p.parse_args()

    atlas_path = Path(args.atlas)
    out_dir = Path(args.out_dir) if args.out_dir else atlas_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = atlas_path.stem
    meta_path = atlas_path.with_suffix(".json")
    anims_path = atlas_path.with_suffix(".anims.json")
    for f in (meta_path, anims_path):
        if not f.exists():
            raise SystemExit(f"error: missing {f} (run sprite_slicer.py first)")

    im = Image.open(atlas_path).convert("RGBA")
    arr = np.asarray(im).astype(np.float32) / 255.0
    rgb, alpha = arr[..., :3], arr[..., 3]
    hsv = rgb_to_hsv(rgb)
    mk = masks(hsv, alpha)
    refs = {k: ref_color(hsv, w) for k, w in mk.items()}
    print("reference (H°,S,V): " + "  ".join(f"{k}=({v[0]:.0f},{v[1]:.2f},{v[2]:.2f})" for k, v in refs.items()))

    palettes = json.loads(Path(args.palettes).read_text(encoding="utf-8"))["palettes"]
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    anims = json.loads(anims_path.read_text(encoding="utf-8"))
    variants = []
    for pal in palettes:
        out_rgb = rgb.copy()
        for region in ("spot", "scarf"):
            if region not in pal:
                continue
            new_rgb, w = recolor(hsv, mk[region], refs[region], hex_to_hsv(pal[region]))
            out_rgb = out_rgb * (1 - w) + new_rgb * w
        res = np.dstack([np.clip(out_rgb, 0, 1), alpha])
        img = Image.fromarray((res * 255 + 0.5).astype(np.uint8), "RGBA")
        name = f"{args.prefix}_{pal['id']}"
        img.save(out_dir / f"{name}.png")
        m = json.loads(json.dumps(meta)); m["meta"]["image"] = f"{name}.png"
        (out_dir / f"{name}.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
        a = json.loads(json.dumps(anims))
        for an in a["anims"]:
            for fr in an["frames"]:
                fr["key"] = name
        (out_dir / f"{name}.anims.json").write_text(json.dumps(a, indent=2), encoding="utf-8")
        variants.append((pal["id"], img))
        print(f"  {name}: spot={pal.get('spot','-')} scarf={pal.get('scarf','-')}")

    # contact sheet: each variant shows down_idle, up_idle, left_idle, down_net
    fs = meta["meta"]["frame_size"]; fw, fh = fs["w"], fs["h"]
    picks = ["down_idle", "up_idle", "left_idle", "down_net"]
    sheet = Image.new("RGBA", (fw * len(picks), fh * len(variants)), (255, 255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for r, (pid, img) in enumerate(variants):
        for c, nm in enumerate(picks):
            entry = meta["frames"][nm]
            fr, off = entry["frame"], entry.get("spriteSourceSize", {"x": 0, "y": 0})
            tile = img.crop((fr["x"], fr["y"], fr["x"] + fr["w"], fr["y"] + fr["h"]))
            sheet.alpha_composite(tile, (c * fw + off["x"], r * fh + off["y"]))
        d.text((6, r * fh + 6), pid, fill=(0, 0, 0, 255))
        d.line([0, (r + 1) * fh - 1, sheet.width, (r + 1) * fh - 1], fill=(200, 200, 200, 255))
    cpath = out_dir / f"{args.prefix}_palettes_contact.png"
    sheet.convert("RGB").save(cpath)
    print(f"wrote {len(variants)} variants + {cpath}")


if __name__ == "__main__":
    main()
