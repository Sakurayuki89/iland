#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema"]
# ///
"""content_lint must pass the real data and fail a deliberately broken fixture."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINT = ROOT / "tools" / "content_lint.py"
BAD = Path(__file__).resolve().parent / "fixtures" / "bad"


def run(*args):
    r = subprocess.run([sys.executable, str(LINT), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


failures = []


def check(cond, label):
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        failures.append(label)


code, out = run()
check(code == 0, f"real data passes (exit {code})")
if code != 0:
    print(out)

code, out = run("--strict")
check(code == 1, "real data fails under --strict while audio/images are not generated yet")

code, out = run("--data-dir", str(BAD), "--root", str(BAD))
check(code == 1, "broken fixture fails")
for needle, label in [
    ("English has 13 words (max 12)", "flags a 13-word sentence"),
    ("elephant", "flags a word outside the unit vocabulary"),
    ("no Hangul", "flags Korean translation without Hangul"),
    ("'ko' is a required property", "flags a missing Korean translation (schema)"),
    ("duplicate line id 'too_long'", "flags duplicate line ids"),
    ("duplicate id 'cat'", "flags duplicate vocab ids"),
]:
    check(needle in out, label)
check("(ok_12)" not in out, "accepts a 12-word sentence (boundary)")

if failures:
    print(f"\n{len(failures)} check(s) failed")
    print(out)
    sys.exit(1)
print("\nall checks passed")
