#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Environment check for Island development.

Read-only: it never installs or changes anything, it only reports what is
missing and the command that fixes it. Secret values are never printed
(only whether a key is set).

Exit code: 1 if a REQUIRED check fails, otherwise 0.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK, WARN, MISS = "ok", "warn", "missing"


def run(cmd: list[str]) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return r.returncode == 0, (r.stdout or r.stderr).strip()


def ver(text: str) -> tuple[int, ...]:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
    return tuple(int(x) for x in m.groups(default="0")) if m else (0, 0, 0)


def check_cmd(cmd: list[str], label: str, fix: str, minimum: tuple[int, ...] | None = None):
    if not shutil.which(cmd[0]):
        return MISS, "not found", fix
    ok, out = run(cmd)
    if not ok:
        return MISS, "installed but not working", fix
    first = out.splitlines()[0] if out else ""
    if minimum and ver(first) < minimum:
        return WARN, f"{first} (need >= {'.'.join(map(str, minimum))})", fix
    return OK, first, ""


def check_app(name: str, fix: str):
    p = Path("/Applications") / f"{name}.app"
    return (OK, str(p), "") if p.exists() else (MISS, "not installed", fix)


def check_repo():
    ok, _ = run(["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"])
    return (OK, "git repository", "") if ok else (MISS, "not a git repository", "git init -b main")


def check_deps():
    p = ROOT / "apps" / "client" / "node_modules"
    return (OK, "apps/client/node_modules", "") if p.exists() else (MISS, "dependencies not installed", "pnpm install")


def check_xcode():
    ok, out = run(["xcodebuild", "-version"])
    if ok:
        return OK, out.splitlines()[0], ""
    return MISS, "full Xcode not active (Command Line Tools alone are not enough)", \
        "App Store -> Xcode, then: sudo xcode-select -s /Applications/Xcode.app"


def check_java():
    if not shutil.which("java"):
        return MISS, "not found", "brew install --cask temurin@17"
    ok, out = run(["java", "-version"])
    if not ok:
        return MISS, "no Java runtime", "brew install --cask temurin@17"
    return OK, out.splitlines()[0], ""


def check_android_sdk():
    cands = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
             str(Path.home() / "Library/Android/sdk")]
    for c in cands:
        if c and Path(c).exists():
            return OK, c, ""
    return MISS, "Android SDK not found", "brew install --cask android-studio  (then open it once to install the SDK)"


def read_env_names() -> set[str]:
    names = {k for k, v in os.environ.items() if v}
    envf = ROOT / ".env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if v.strip():
                    names.add(k.strip())
    return names


def check_key(name: str, names: set[str]):
    return (OK, "set", "") if name in names else (MISS, "not set", f"add {name}=... to .env (see .env.example)")


def groups():
    env_names = read_env_names()
    return [
        ("REQUIRED  core development", True, [
            ("node >= 20.19", lambda: check_cmd(["node", "--version"], "node", "brew install node@22", (20, 19))),
            ("pnpm", lambda: check_cmd(["pnpm", "--version"], "pnpm", "corepack enable  (or: brew install pnpm)")),
            ("uv (runs tools/*.py)", lambda: check_cmd(["uv", "--version"], "uv", "brew install uv")),
            ("git", lambda: check_cmd(["git", "--version"], "git", "xcode-select --install")),
            ("ffmpeg (audio/video)", lambda: check_cmd(["ffmpeg", "-version"], "ffmpeg", "brew install ffmpeg")),
            ("git repository", check_repo),
            ("client dependencies", check_deps),
        ]),
        ("RECOMMENDED  authoring", False, [
            ("Tiled (map editor)", lambda: check_app("Tiled", "brew install --cask tiled")),
            ("Google Chrome (headless checks)", lambda: check_app("Google Chrome", "brew install --cask google-chrome")),
        ]),
        ("MOBILE  only for iOS/Android builds", False, [
            ("Xcode", check_xcode),
            ("Java JDK", check_java),
            ("Android SDK", check_android_sdk),
        ]),
        ("KEYS  only for TTS / NPC chat (values are never shown)", False, [
            ("GEMINI_API_KEY", lambda: check_key("GEMINI_API_KEY", env_names)),
            ("FISH_API_KEY", lambda: check_key("FISH_API_KEY", env_names)),
            ("ANTHROPIC_API_KEY", lambda: check_key("ANTHROPIC_API_KEY", env_names)),
        ]),
    ]


def main() -> int:
    mark = {OK: "ok  ", WARN: "warn", MISS: "MISS"}
    required_failed = 0
    totals = {OK: 0, WARN: 0, MISS: 0}
    for title, required, checks in groups():
        print(f"\n{title}")
        for label, fn in checks:
            status, detail, fix = fn()
            totals[status] += 1
            print(f"  [{mark[status]}] {label:<34} {detail}")
            if status != OK and fix:
                print(f"         fix: {fix}")
            if required and status != OK:
                required_failed += 1
    print(f"\n{totals[OK]} ok, {totals[WARN]} warning(s), {totals[MISS]} missing"
          + (f"  -> {required_failed} REQUIRED item(s) need attention" if required_failed else ""))
    return 1 if required_failed else 0


if __name__ == "__main__":
    sys.exit(main())
