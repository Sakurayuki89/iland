#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy", "scipy"]
# ///
"""Slice an AI-generated character sheet into an aligned Phaser atlas.

Input : a sheet with a white background laid out as ROWS x COLS cells
        (default 3 x 4: rows = down/up/left, cols = idle/walk_a/walk_b/net).
Output: <key>.png (atlas), <key>.json (Phaser hash atlas), <key>.anims.json
        (Phaser anims.fromJSON format + flipX), <key>_contact.png (review sheet).

The original image is only read, never modified.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage, signal
from _common import utf8_output

ROW_NAMES = ["down", "up", "left"]
COL_NAMES = ["idle", "walk_a", "walk_b", "net"]


def remove_background(rgb: np.ndarray, tol: int, clear_enclosed: bool, min_hole: int) -> np.ndarray:
    """Return RGBA. Only near-white regions connected to the image border are removed,
    so cream fur / highlights enclosed by the dark outline survive."""
    minc = rgb.min(axis=2)
    cand = minc >= 255 - tol
    lab, n = ndimage.label(cand)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    is_bg_label = np.zeros(n + 1, dtype=bool)
    is_bg_label[border] = True
    is_bg_label[0] = False
    bg = is_bg_label[lab]

    if clear_enclosed:  # e.g. the insides of the bug-net mesh
        pure = (minc >= 250) & ~bg
        lab2, n2 = ndimage.label(pure)
        if n2:
            sizes = ndimage.sum(pure, lab2, index=np.arange(1, n2 + 1))
            big = np.zeros(n2 + 1, dtype=bool)
            big[1:] = sizes >= min_hole
            bg |= big[lab2]

    alpha = np.where(bg, 0.0, 1.0)
    out = rgb.astype(np.float32).copy()

    # Anti-aliased rim: estimate coverage from darkness and un-matte from white.
    band = ndimage.binary_dilation(bg, iterations=2) & ~bg
    edge_ref = 90.0  # rough darkness of the brown outline
    a = np.clip((255.0 - minc[band]) / (255.0 - edge_ref), 0.0, 1.0)
    alpha[band] = a
    safe = np.maximum(a, 1e-3)[:, None]
    out[band] = np.clip((out[band] - 255.0 * (1.0 - a)[:, None]) / safe, 0, 255)

    rgba = np.dstack([out, alpha * 255.0]).round().astype(np.uint8)
    rgba[alpha == 0] = 0
    return rgba


def find_cells(alpha: np.ndarray, rows: int, cols: int, merge_gap: int, min_area: int):
    """Connected components -> exactly rows*cols cells ordered row-major."""
    fg = alpha > 40
    merged = ndimage.binary_dilation(fg, iterations=merge_gap)
    lab, n = ndimage.label(merged)
    objs = ndimage.find_objects(lab)
    comps = []
    for i, sl in enumerate(objs, start=1):
        area = int(((lab[sl] == i) & fg[sl]).sum())
        if area < min_area:
            continue
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        comps.append({"id": i, "box": (x0, y0, x1, y1), "area": area,
                      "cy": (y0 + y1) / 2, "cx": (x0 + x1) / 2})
    want = rows * cols
    if len(comps) < want:
        sizes = sorted(c["area"] for c in comps)
        sys.exit(f"error: found {len(comps)} cells, expected {want}. "
                 f"areas={sizes}. Try --merge-gap / --min-area / --tol.")
    comps.sort(key=lambda c: -c["area"])
    cells, strays = comps[:want], comps[want:]
    for c in cells:
        c["ids"] = [c["id"]]

    def gap(p, q):  # distance between two boxes (0 if they overlap)
        dx = max(q[0] - p[2], p[0] - q[2], 0)
        dy = max(q[1] - p[3], p[1] - q[3], 0)
        return (dx * dx + dy * dy) ** 0.5

    for sc in strays:  # a piece drawn apart from its body, e.g. a net hoop behind the head
        host = min(cells, key=lambda c: gap(c["box"], sc["box"]))
        print(f"note: attached a detached piece ({sc['area']} px, {gap(host['box'], sc['box']):.0f} px away) to its nearest cell")
        hb, sb = host["box"], sc["box"]
        host["box"] = (min(hb[0], sb[0]), min(hb[1], sb[1]), max(hb[2], sb[2]), max(hb[3], sb[3]))
        host["ids"].append(sc["id"])
        host["cx"], host["cy"] = (host["box"][0] + host["box"][2]) / 2, (host["box"][1] + host["box"][3]) / 2
    comps = cells
    comps.sort(key=lambda c: c["cy"])
    ordered = []
    for r in range(rows):
        row = sorted(comps[r * cols:(r + 1) * cols], key=lambda c: c["cx"])
        ordered.extend(row)
    return ordered, lab


def crop_cell(rgba: np.ndarray, lab: np.ndarray, comp: dict) -> np.ndarray:
    x0, y0, x1, y1 = comp["box"]
    sub = rgba[y0:y1, x0:x1].copy()
    mask = np.isin(lab[y0:y1, x0:x1], comp["ids"])
    sub[~mask] = 0
    ys, xs = np.nonzero(sub[..., 3] > 8)
    return sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _ramp(x, lo, hi):
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def _hsv(rgb: np.ndarray):
    """rgb float 0..1 -> hue (deg), saturation, value."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    safe = np.maximum(d, 1e-6)
    h = np.where(mx == r, ((g - b) / safe) % 6, np.where(mx == g, (b - r) / safe + 2, (r - g) / safe + 4)) * 60.0
    h = np.where(d > 1e-6, h, 0.0)
    return h, np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0), mx


def _marking_weight(frame: np.ndarray, hue_lo: float, hue_hi: float, head: float = 0.5):
    rgb = frame[..., :3].astype(np.float32) / 255.0
    opaque = frame[..., 3] > 128
    h, s, v = _hsv(rgb)
    region = np.zeros_like(opaque)
    region[: int(opaque.shape[0] * head)] = True  # head only: leaves a same-coloured tail tip alone
    w = _ramp(h, hue_lo, hue_lo + 5) * (1 - _ramp(h, hue_hi - 5, hue_hi)) * _ramp(s, 0.22, 0.4) * _ramp(v, 0.55, 0.75) * opaque * region
    return w, rgb, s, v, opaque


def _head_frame(opaque: np.ndarray) -> tuple[float, int, float]:
    """Head centre x, skull-top y (below the ear tips) and head width, from the silhouette."""
    hgt = opaque.shape[0]
    count = opaque[: int(hgt * 0.55)].sum(1)
    top = int(np.nonzero(count >= 0.6 * count.max())[0].min())
    spans = [np.nonzero(r)[0] for r in opaque[top: int(hgt * 0.5)] if r.any()]
    width = float(max(x.max() - x.min() for x in spans))
    cx = float(np.median([(x.min() + x.max()) / 2 for x in spans]))
    return cx, top, width


def copy_marking(ref: np.ndarray, tgt: np.ndarray, hue_lo: float, hue_hi: float) -> tuple[np.ndarray, int]:
    """Mirroring a cell puts a one-sided head marking (e.g. one orange ear) on the wrong side.
    Erase it there and repaint the marking of `ref` (the row's idle cell), aligned by head position
    and size, so every frame of the row carries the same marking on the same ear.
    Returns (frame, painted pixel count)."""
    w_ref, rgb_ref, *_ = _marking_weight(ref, hue_lo, hue_hi)
    w_tgt, rgb, s, v, opaque = _marking_weight(tgt, hue_lo, hue_hi)
    if (w_ref > 0.5).sum() < 40:
        return tgt, 0
    cx_r, top_r, wid_r = _head_frame(ref[..., 3] > 128)
    cx_t, top_t, wid_t = _head_frame(opaque)
    k = wid_t / wid_r

    yy, xx = np.mgrid[0:opaque.shape[0], 0:opaque.shape[1]]
    rx = np.round((xx - cx_t) / k + cx_r).astype(int)
    ry = np.round((yy - top_t) / k + top_r).astype(int)
    ok = (rx >= 0) & (rx < ref.shape[1]) & (ry >= 0) & (ry < ref.shape[0])
    w_new = np.zeros_like(w_tgt)
    w_new[ok] = w_ref[ry[ok], rx[ok]]
    col_new = np.zeros_like(rgb)
    col_new[ok] = rgb_ref[ry[ok], rx[ok]]

    cream = np.median(rgb[opaque & (s < 0.18) & (v > 0.9)], axis=0)
    out = rgb * (1 - w_tgt[..., None]) + cream * w_tgt[..., None]  # erase the misplaced marking
    # paint only onto plain fur (or where the old marking was): outline, eyes and blush stay untouched
    fillable = np.maximum(_ramp(v, 0.78, 0.92) * (1 - _ramp(s, 0.14, 0.30)), w_tgt) * opaque
    wt = (w_new * fillable)[..., None]
    out = out * (1 - wt) + col_new * wt
    res = tgt.copy()
    res[..., :3] = np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return res, int((wt[..., 0] > 0.5).sum())


def feet_center_x(frame: np.ndarray) -> float:
    a = frame[..., 3] > 128
    h = a.shape[0]
    ys, xs = np.nonzero(a[int(h * 0.92):])
    return float(np.median(xs))


def register_dx(ref: np.ndarray, frm: np.ndarray, scale: int = 4) -> float:
    """x offset (in px) that places `frm` over `ref` with bottoms aligned."""
    r = ndimage.gaussian_filter((ref[..., 3] > 128).astype(np.float32)[::scale, ::scale], 1)
    f = ndimage.gaussian_filter((frm[..., 3] > 128).astype(np.float32)[::scale, ::scale], 1)
    corr = signal.fftconvolve(r, f[::-1, ::-1], mode="full")
    # row index in `corr` for shift dy: py = dy + f.h - 1 ; bottom aligned -> dy = r.h - f.h
    py0 = (r.shape[0] - f.shape[0]) + f.shape[0] - 1
    lo, hi = max(py0 - 3, 0), min(py0 + 4, corr.shape[0])
    band = corr[lo:hi]
    _, px = np.unravel_index(np.argmax(band), band.shape)
    return float((px - (f.shape[1] - 1)) * scale)


def build(args) -> None:
    src = Path(args.sheet)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rgb = np.asarray(Image.open(src).convert("RGB"))
    print(f"sheet {src.name}: {rgb.shape[1]}x{rgb.shape[0]}")

    rgba = remove_background(rgb, args.tol, args.clear_enclosed, args.min_hole)
    cells, lab = find_cells(rgba[..., 3], args.rows, args.cols, args.merge_gap, args.min_area)
    frames = [crop_cell(rgba, lab, c) for c in cells]

    # AI sheets sometimes draw a cell facing the wrong way; mirror those so a row faces one direction.
    cell_names = [f"{ROW_NAMES[i // args.cols]}_{COL_NAMES[i % args.cols]}" for i in range(len(frames))]
    extras = []  # (path, column names); a column called "ref" is a standing reference used only for scale
    for spec in args.extra:
        path, _, cols_s = spec.rpartition(":")
        ecols = [c.strip() for c in cols_s.split(",") if c.strip()]
        if not path or not ecols:
            sys.exit(f"error: --extra expects PATH:col1,col2 (got {spec!r})")
        extras.append((Path(path), ecols))
    extra_names = [f"{r}_{c}" for _, ecols in extras for r in ROW_NAMES[: args.rows] for c in ecols if c != "ref"]
    dup = sorted(set(extra_names) & set(cell_names)) + sorted({n for n in extra_names if extra_names.count(n) > 1})
    if dup:
        sys.exit(f"error: --extra cell names already exist: {dup}")
    flip = [n.strip() for n in args.flip.split(",") if n.strip()]
    unknown = [n for n in flip if n not in cell_names + extra_names]
    if unknown:
        sys.exit(f"error: --flip names not in the sheet: {unknown}. valid: {cell_names + extra_names}")
    hue = [float(x) for x in args.marking_hue.split(",")] if args.marking_hue else None
    if hue and len(hue) != 2:
        sys.exit("error: --marking-hue needs two numbers, e.g. 12,50")
    for i, n in enumerate(cell_names):
        if n in flip:
            frames[i] = np.ascontiguousarray(frames[i][:, ::-1])
            note = ""
            if hue:
                ref = frames[(i // args.cols) * args.cols]  # the row's idle cell
                frames[i], painted = copy_marking(ref, frames[i], hue[0], hue[1])
                note = f" (marking copied from idle: {painted} px)" if painted else " (no marking found in idle)"
            print(f"mirrored: {n}{note}")

    # pivots (x), bottom-aligned (y)
    pivots = [0.0] * len(frames)
    offsets = {}
    for r in range(args.rows):
        ref_i = r * args.cols  # idle of this row
        ref = frames[ref_i]
        pivots[ref_i] = feet_center_x(ref)
        for c in range(1, args.cols):
            i = r * args.cols + c
            if args.pivot_x == "register":
                ox = register_dx(ref, frames[i])
                pivots[i] = pivots[ref_i] - ox
                offsets[i] = ox
            else:
                pivots[i] = feet_center_x(frames[i])

    # extra pose sheets (e.g. fallen): scaled to the main sheet via their standing "ref" column,
    # centred on their own silhouette and bottom-aligned like every other frame
    names = list(cell_names)
    for path, ecols in extras:
        ergb = np.asarray(Image.open(path).convert("RGB"))
        # never clear enclosed whites here: that option is for the net mesh and would punch out eye whites
        ergba = remove_background(ergb, args.tol, False, args.min_hole)
        ecells, elab = find_cells(ergba[..., 3], args.rows, len(ecols), args.merge_gap, args.min_area)
        ef = [crop_cell(ergba, elab, c) for c in ecells]
        k = 1.0
        if "ref" in ecols:
            rc = ecols.index("ref")
            k = float(np.median([frames[r * args.cols].shape[0] / ef[r * len(ecols) + rc].shape[0] for r in range(args.rows)]))
        else:
            print(f"warning: {path.name} has no 'ref' column; using its scale as-is")
        print(f"extra {path.name}: columns {ecols}, scale x{k:.3f}")
        for r in range(args.rows):
            for c, cname in enumerate(ecols):
                if cname == "ref":
                    continue
                f = ef[r * len(ecols) + c]
                if abs(k - 1) > 0.01:
                    f = np.asarray(Image.fromarray(f, "RGBA").resize((max(1, round(f.shape[1] * k)), max(1, round(f.shape[0] * k))), Image.LANCZOS))
                name = f"{ROW_NAMES[r]}_{cname}"
                if name in flip:
                    f = np.ascontiguousarray(f[:, ::-1])
                    print(f"mirrored: {name}")
                idle_i = r * args.cols
                if f.shape[0] >= 0.8 * frames[idle_i].shape[0]:
                    # still standing: line the body up with the row's idle, like the main frames
                    pivots.append(pivots[idle_i] - register_dx(frames[idle_i], f))
                else:
                    # lying down: centre on the silhouette
                    pivots.append(float(np.nonzero(f[..., 3] > 128)[1].mean()))
                frames.append(f)
                names.append(name)

    pad = args.pad
    left = max(p for p in pivots) + pad
    right = max(f.shape[1] - p for f, p in zip(frames, pivots)) + pad
    half = int(np.ceil(max(left, right)))
    W = half * 2
    H = int(max(f.shape[0] for f in frames)) + pad * 2
    pivot_y = H - pad

    canon = []
    for f, p in zip(frames, pivots):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        x = int(round(half - p))
        y = pivot_y - f.shape[0]
        im.alpha_composite(Image.fromarray(f, "RGBA"), (x, y))
        canon.append(im)

    # Scale is anchored to the standing character (row 1 idle), so adding taller or wider poses
    # grows the frame but never shrinks the character.
    scale = args.char_height / frames[0].shape[0]
    fw, fh = max(1, round(W * scale)), max(1, round(H * scale))
    final = [im.resize((fw, fh), Image.LANCZOS) for im in canon]
    piv_y_final = round(pivot_y * scale)

    # Trim every frame to its opaque pixels and pack tightly: the atlas holds only the drawn area,
    # while sourceSize/spriteSourceSize keep each frame's logical cell and pivot unchanged for the engine.
    boxes = [im.getbbox() or (0, 0, 1, 1) for im in final]
    pos, aw, ah = pack_shelves([(b[2] - b[0], b[3] - b[1]) for b in boxes], args.atlas_width)
    atlas = Image.new("RGBA", (aw, ah), (0, 0, 0, 0))
    hashed = {}
    for im, name, (bx0, by0, bx1, by1), (x, y) in zip(final, names, boxes, pos):
        atlas.alpha_composite(im.crop((bx0, by0, bx1, by1)), (x, y))
        hashed[name] = {
            "frame": {"x": x, "y": y, "w": bx1 - bx0, "h": by1 - by0},
            "rotated": False, "trimmed": True,
            "spriteSourceSize": {"x": bx0, "y": by0, "w": bx1 - bx0, "h": by1 - by0},
            "sourceSize": {"w": fw, "h": fh},
            "pivot": {"x": 0.5, "y": round(piv_y_final / fh, 4)},
        }
    key = args.key
    atlas.save(out / f"{key}.png")
    meta = {"app": "island/tools/sprite_slicer.py", "image": f"{key}.png", "format": "RGBA8888",
            "size": {"w": atlas.width, "h": atlas.height}, "scale": "1",
            "source": src.name, "extra": [e[0].name for e in extras], "frame_size": {"w": fw, "h": fh},
            "char_height": args.char_height,
            "origin": {"x": 0.5, "y": round(piv_y_final / fh, 4)}}
    (out / f"{key}.json").write_text(json.dumps({"frames": hashed, "meta": meta}, indent=2), encoding="utf-8")

    # Phaser anims.fromJSON (+ flipX, which Phaser ignores; the client applies it)
    def anim(k, frame_names, fps, repeat, flip=False):
        return {"key": k, "type": "frame", "frameRate": fps, "repeat": repeat, "flipX": flip,
                "frames": [{"key": key, "frame": n} for n in frame_names]}

    anims = []
    for direction, src_dir, flip in [("down", "down", False), ("up", "up", False),
                                     ("left", "left", False), ("right", "left", True)]:
        anims.append(anim(f"idle_{direction}", [f"{src_dir}_idle"], 1, -1, flip))
        anims.append(anim(f"walk_{direction}", [f"{src_dir}_idle", f"{src_dir}_walk_a",
                                                f"{src_dir}_idle", f"{src_dir}_walk_b"], args.walk_fps, -1, flip))
        anims.append(anim(f"net_{direction}", [f"{src_dir}_net"], 1, 0, flip))
    (out / f"{key}.anims.json").write_text(json.dumps({"anims": anims, "globalTimeScale": 1}, indent=2), encoding="utf-8")

    make_contact(final, names, fw, fh, piv_y_final, args.cols, out / f"{key}_contact.png")

    untrimmed = fw * fh * len(final)
    print(f"frames: {len(final)}  frame size {fw}x{fh}  pivot y={piv_y_final}px  atlas {atlas.width}x{atlas.height} "
          f"({atlas.width * atlas.height * 4 / 1e6:.1f} MB on GPU, {100 * atlas.width * atlas.height / untrimmed:.0f}% of untrimmed)")
    if offsets:
        worst = max(abs(v) for v in offsets.values())
        print(f"registration: largest x shift vs idle = {worst:.0f}px (source px)")
        for i, ox in sorted(offsets.items()):
            flag = "  <-- large" if abs(ox) > 0.12 * W else ""
            print(f"  {names[i]:<14} dx={ox:+6.1f}{flag}")
    print(f"wrote: {out / (key + '.png')}, .json, .anims.json, _contact.png")


def pack_shelves(sizes: list[tuple[int, int]], max_w: int, pad: int = 2):
    """Shelf packing, tallest first. Returns top-left positions in input order and the sheet size."""
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    pos: list[tuple[int, int]] = [(0, 0)] * len(sizes)
    x = y = pad
    shelf = width = 0
    for i in order:
        w, h = sizes[i]
        if x + w + pad > max_w and x > pad:
            x, y, shelf = pad, y + shelf + pad, 0
        pos[i] = (x, y)
        x += w + pad
        shelf = max(shelf, h)
        width = max(width, x)
    return pos, width, y + shelf + pad


def make_contact(frames, names, fw, fh, piv_y, cols, path):
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGBA", (fw * cols, fh * rows), (255, 255, 255, 255))
    d = ImageDraw.Draw(sheet)
    tile = 16
    for y in range(0, sheet.height, tile):
        for x in range(0, sheet.width, tile):
            if (x // tile + y // tile) % 2:
                d.rectangle([x, y, x + tile - 1, y + tile - 1], fill=(232, 232, 232, 255))
    for i, (im, n) in enumerate(zip(frames, names)):
        x, y = (i % cols) * fw, (i // cols) * fh
        sheet.alpha_composite(im, (x, y))
        d.line([x, y + piv_y, x + fw, y + piv_y], fill=(255, 0, 80, 255))
        d.line([x + fw // 2, y, x + fw // 2, y + fh], fill=(0, 120, 255, 255))
        d.rectangle([x, y, x + fw - 1, y + fh - 1], outline=(150, 150, 150, 255))
        d.text((x + 4, y + 4), n, fill=(0, 0, 0, 255))
    sheet.convert("RGB").save(path)


def main():
    utf8_output()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sheet", help="input sheet PNG (white background)")
    p.add_argument("-o", "--out-dir", default="assets/sprites")
    p.add_argument("--key", default="cat_base", help="texture key / output file stem")
    p.add_argument("--rows", type=int, default=3)
    p.add_argument("--cols", type=int, default=4)
    p.add_argument("--char-height", type=int, default=183, help="height in px of the standing character (first row idle); "
                                                                 "frame size follows from the poses")
    p.add_argument("--tol", type=int, default=14, help="near-white tolerance for background")
    p.add_argument("--clear-enclosed", action="store_true", help="also clear enclosed pure-white holes (net mesh)")
    p.add_argument("--min-hole", type=int, default=80, help="min area (px) of an enclosed hole to clear")
    p.add_argument("--merge-gap", type=int, default=6, help="dilation (px) to join parts of one cell")
    p.add_argument("--min-area", type=int, default=2000, help="ignore specks smaller than this (px)")
    p.add_argument("--pad", type=int, default=12, help="transparent padding (source px)")
    p.add_argument("--pivot-x", choices=["register", "feet"], default="register")
    p.add_argument("--walk-fps", type=int, default=8)
    p.add_argument("--atlas-width", type=int, default=1024, help="max atlas width in px (frames are trimmed and packed)")
    p.add_argument("--flip", default="", help="comma-separated cells to mirror, e.g. left_walk_a,left_walk_b")
    p.add_argument("--extra", action="append", default=[], metavar="PATH:COLS",
                   help="add poses from another sheet with the same rows, e.g. fall.png:ref,fallen "
                        "('ref' = standing reference column, used for scale and then dropped). Repeatable.")
    p.add_argument("--marking-hue", default="", help="hue range (deg) of a one-sided head marking, e.g. 18,50 for orange; "
                                                      "mirrored cells get the row's idle marking repainted on the right side")
    build(p.parse_args())


if __name__ == "__main__":
    main()
