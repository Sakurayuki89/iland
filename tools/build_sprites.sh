#!/bin/sh
# Rebuild every character atlas in assets/sprites from the source sheets in content/.
# The flags are per-sheet fixes for how each AI sheet was drawn (see tools/README.md) — keep them here,
# not in anyone's memory. Each extra sheet is PATH:columns, where "ref" is a standing reference for scale.
set -eu
cd "$(dirname "$0")/.."

# Orange-patch cat: side-row walk cells were drawn facing right (mirror them, then repaint the ear
# patch from the idle cell); the net mesh is pure white inside and is made see-through.
uv run tools/sprite_slicer.py content/hf_20260930_044638_974561b7-2e7c-4665-a6b9-ebce2793c31d.png \
  --key cat_base --clear-enclosed --flip left_walk_a,left_walk_b --marking-hue 18,50 \
  --extra content/cat_fall_755fadb8.png:ref,fallen \
  --extra content/cat_expr_96f6ba09.png:ref,joy,surprised \
  --extra content/cat_swing_1b276bc2.png:ref,net_up,net_down

# Siamese cat: only the side-row net cell faces right. Markings are symmetric, so mirroring is safe.
# No --clear-enclosed: its net fill is off-white (would clear in patches) and its eyes have white highlights.
uv run tools/sprite_slicer.py content/siamese_base_cdd7fe89.png \
  --key siamese_base --flip left_net \
  --extra content/siamese_fall_7f561538.png:ref,fallen \
  --extra content/siamese_expr_83bac47a.png:ref,joy,surprised \
  --extra content/siamese_swing_9373c1b6.png:ref,net_up,net_down

# Colour variants of the orange-patch cat (spot + scarf).
uv run tools/palette_swap.py
