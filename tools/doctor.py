#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Environment check for Island development (macOS, Windows, Linux).

Read-only: it never installs or changes anything, it only reports what is
missing and the command that fixes it. Secret values are never printed
(only whether a key is set).

Exit code: 1 if a REQUIRED check fails, otherwise 0.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from _common import IS_MAC, IS_WINDOWS, find_chrome, run_text, utf8_output, which

ROOT = Path(__file__).resolve().parent.parent
OK, WARN, MISS, SKIP = "ok", "warn", "missing", "n/a"


def pick(mac: str, win: str, other: str = "") -> str:
    """Install hint for the current OS."""
    return win if IS_WINDOWS else mac if IS_MAC else (other or mac)


def run(cmd: list[str]) -> tuple[bool, str]:
    try:
        r = run_text(cmd)
    except (OSError, Exception):  # missing program, timeout, ...
        return False, ""
    return r.returncode == 0, (r.stdout or r.stderr).strip()


def ver(text: str) -> tuple[int, ...]:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
    return tuple(int(x) for x in m.groups(default="0")) if m else (0, 0, 0)


def check_cmd(cmd: list[str], fix: str, minimum: tuple[int, ...] | None = None):
    if not which(cmd[0]):
        return MISS, "not found", fix
    ok, out = run(cmd)
    if not ok:
        return MISS, "installed but not working", fix
    first = out.splitlines()[0] if out else ""
    if minimum and ver(first) < minimum:
        return WARN, f"{first} (need >= {'.'.join(map(str, minimum))})", fix
    return OK, first, ""


def tiled_paths() -> list[Path]:
    if IS_MAC:
        return [Path("/Applications/Tiled.app")]
    if IS_WINDOWS:
        roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        return [Path(r) / "Tiled" / "tiled.exe" for r in roots if r] + [Path(r) / "Programs" / "Tiled" / "tiled.exe" for r in roots if r]
    return []


def check_tiled():
    fix = pick("brew install --cask tiled", "download the installer from https://www.mapeditor.org/ (or: winget search tiled)", "sudo apt install tiled")
    for p in tiled_paths():
        if p.exists():
            return OK, str(p), ""
    exe = which("tiled")
    return (OK, exe, "") if exe else (MISS, "not installed", fix)


def check_chrome():
    exe = find_chrome()
    if exe:
        return OK, exe, ""
    return MISS, "Chrome/Edge not found (set CHROME_PATH if it is installed elsewhere)", pick("brew install --cask google-chrome", "winget install Google.Chrome")


def check_repo():
    ok, _ = run(["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"])
    return (OK, "git repository", "") if ok else (MISS, "not a git repository", "git init -b main")


def check_deps():
    p = ROOT / "apps" / "client" / "node_modules"
    return (OK, "apps/client/node_modules", "") if p.exists() else (MISS, "dependencies not installed", "pnpm install")


def check_xcode():
    if not IS_MAC:
        return SKIP, "iOS builds need a Mac", ""
    ok, out = run(["xcodebuild", "-version"])
    if ok:
        return OK, out.splitlines()[0], ""
    return MISS, "full Xcode not active (Command Line Tools alone are not enough)", \
        "App Store -> Xcode, then: sudo xcode-select -s /Applications/Xcode.app"


def check_java():
    fix = pick("brew install --cask temurin@17", "winget install EclipseAdoptium.Temurin.17.JDK", "sudo apt install openjdk-17-jdk")
    if not which("java"):
        return MISS, "not found", fix
    ok, out = run(["java", "-version"])
    if not ok:
        return MISS, "no Java runtime", fix
    return OK, out.splitlines()[0], ""


def check_android_sdk():
    default = (Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk") if IS_WINDOWS else Path.home() / ("Library/Android/sdk" if IS_MAC else "Android/Sdk")
    for c in [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"), str(default)]:
        if c and Path(c).exists():
            return OK, c, ""
    fix = pick("brew install --cask android-studio", "winget install Google.AndroidStudio")
    return MISS, "Android SDK not found", f"{fix}  (then open it once to install the SDK)"


def read_env_names() -> set[str]:
    names = {k for k, v in os.environ.items() if v}
    envf = ROOT / ".env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8-sig").splitlines():
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
            ("node >= 20.19", lambda: check_cmd(["node", "--version"], pick("brew install node@22", "winget install OpenJS.NodeJS.LTS"), (20, 19))),
            ("pnpm", lambda: check_cmd(["pnpm", "--version"], "corepack enable  (or: npm install -g pnpm)")),
            ("uv (runs tools/*.py)", lambda: check_cmd(["uv", "--version"], pick("brew install uv", "winget install astral-sh.uv"))),
            ("git", lambda: check_cmd(["git", "--version"], pick("xcode-select --install", "winget install Git.Git"))),
            ("ffmpeg (audio/video)", lambda: check_cmd(["ffmpeg", "-version"], pick("brew install ffmpeg", "winget install Gyan.FFmpeg"))),
            ("git repository", check_repo),
            ("client dependencies", check_deps),
        ]),
        ("RECOMMENDED  authoring", False, [
            ("Tiled (map editor)", check_tiled),
            ("Chrome/Edge (headless checks)", check_chrome),
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
    utf8_output()
    mark = {OK: "ok  ", WARN: "warn", MISS: "MISS", SKIP: "n/a "}
    required_failed = 0
    totals = {OK: 0, WARN: 0, MISS: 0, SKIP: 0}
    platform = "Windows" if IS_WINDOWS else "macOS" if IS_MAC else "Linux"
    print(f"platform: {platform}")
    for title, required, checks in groups():
        print(f"\n{title}")
        for label, fn in checks:
            status, detail, fix = fn()
            totals[status] += 1
            print(f"  [{mark[status]}] {label:<34} {detail}")
            if status in (WARN, MISS) and fix:
                print(f"         fix: {fix}")
            if required and status in (WARN, MISS):
                required_failed += 1
    print(f"\n{totals[OK]} ok, {totals[WARN]} warning(s), {totals[MISS]} missing, {totals[SKIP]} n/a"
          + (f"  -> {required_failed} REQUIRED item(s) need attention" if required_failed else ""))
    return 1 if required_failed else 0


if __name__ == "__main__":
    sys.exit(main())
