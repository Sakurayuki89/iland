#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Rebuild every character atlas in assets/sprites from the source sheets in content/.

Runs the same on macOS, Windows and Linux (no shell needed). The flags are per-sheet fixes for how each
AI sheet was drawn (see tools/README.md) — keep them here, not in anyone's memory.
Each extra sheet is PATH:columns, where "ref" is a standing reference column used for scale only.

  uv run tools/build_sprites.py              # everything
  uv run tools/build_sprites.py siamese_base # one character
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _common import resolve_cmd, utf8_output

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

# Orange-patch cat: side-row walk cells were drawn facing right (mirror them, then repaint the ear patch
# from the idle cell); the net mesh is pure white inside and is made see-through.
# Siamese cat: only the side-row net cell faces right. Markings are symmetric, so mirroring is safe.
# No --clear-enclosed there: its net fill is off-white (would clear in patches) and its eyes have white highlights.
JOBS: dict[str, list[str]] = {
    "cat_base": [
        "content/hf_20260930_044638_974561b7-2e7c-4665-a6b9-ebce2793c31d.png",
        "--key", "cat_base", "--clear-enclosed", "--flip", "left_walk_a,left_walk_b", "--marking-hue", "18,50",
        "--extra", "content/cat_fall_755fadb8.png:ref,fallen",
        "--extra", "content/cat_expr_96f6ba09.png:ref,joy,surprised",
        "--extra", "content/cat_swing_1b276bc2.png:ref,net_up,net_down",
    ],
    "siamese_base": [
        "content/siamese_base_cdd7fe89.png",
        "--key", "siamese_base", "--flip", "left_net",
        "--extra", "content/siamese_fall_7f561538.png:ref,fallen",
        "--extra", "content/siamese_expr_83bac47a.png:ref,joy,surprised",
        "--extra", "content/siamese_swing_9373c1b6.png:ref,net_up,net_down",
    ],
    # NPCs: 4th column is a talk pose. The collector is a kitten, so it stands shorter.
    "npc_professor": ["content/npc_professor_ff4a5bc6.png", "--key", "npc_professor", "--action", "talk"],
    "npc_collector": ["content/npc_collector_13bc7d95.png", "--key", "npc_collector", "--action", "cheer",
                      "--char-height", "160"],
    "npc_fisher": ["content/npc_fisher_9becd3ba.png", "--key", "npc_fisher", "--action", "cast"],
}

# Insects: 3x4 like the cats; walk = flap/step loop, 4th column = flee. Heights are 2x world px
# (docs/ISLAND_LAYOUT.md: insects are 24-48 world px so kids can tap them).
INSECT_HEIGHT = {"butterfly": 70, "bee": 56, "dragonfly": 80, "grasshopper": 56, "rhinobeetle": 64,
                 "stagbeetle": 70, "firefly": 50, "cricket": 56, "moth": 70, "jewelbeetle": 56,
                 # rain / lake creatures (docs/WEATHER_AND_SPAWN.md §6), Grok sheets at 1280x720
                 "worm": 50, "snail": 56, "waterbeetle": 56, "waterstrider": 60}
INSECT_SHEET = {"butterfly": "9fedf07a", "bee": "fb563e61", "dragonfly": "3c33ec81", "grasshopper": "85f3fa3f",
                "rhinobeetle": "7879dc56", "stagbeetle": "ad75853b", "firefly": "d471284d", "cricket": "dde75699",
                "moth": "847801db", "jewelbeetle": "4f8e16af",
                "worm": "40301fe4", "snail": "baac48e1", "waterbeetle": "0ee04ae0", "waterstrider": "87cf2c39"}
for _name, _h in INSECT_HEIGHT.items():
    JOBS[f"insect_{_name}"] = [f"content/insect_{_name}_{INSECT_SHEET[_name]}.png", "-o", "assets/insects",
                               "--key", f"insect_{_name}", "--action", "flee", "--char-height", str(_h),
                               "--min-area", "800", "--pivot-x", "feet"]  # wings change shape: centre, don't register


def uv_run(script: str, *args: str) -> int:
    cmd = resolve_cmd(["uv", "run", str(TOOLS / script), *args])
    return subprocess.run(cmd, cwd=ROOT).returncode


def main() -> int:
    utf8_output()
    wanted = sys.argv[1:] or list(JOBS)
    unknown = [w for w in wanted if w not in JOBS]
    if unknown:
        print(f"unknown character(s): {unknown}. known: {list(JOBS)}", file=sys.stderr)
        return 2
    for key in wanted:
        print(f"== {key}", flush=True)
        if uv_run("sprite_slicer.py", *JOBS[key]):
            return 1
    if "cat_base" in wanted:
        print("== colour variants of cat_base", flush=True)
        if uv_run("palette_swap.py"):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
