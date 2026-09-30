#!/bin/sh
# Thin wrapper: the real logic lives in tools/build_sprites.py so it also works on Windows without a shell.
set -eu
cd "$(dirname "$0")/.."
exec uv run tools/build_sprites.py "$@"
