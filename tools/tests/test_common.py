#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Browser discovery and command resolution must behave per platform. Runs on any OS (paths are simulated)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import chrome_candidates, find_chrome, resolve_cmd  # noqa: E402

failures: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("ok   " if cond else "FAIL ") + label)
    if not cond:
        failures.append(label)


WIN_ENV = {"PROGRAMFILES": r"C:\Program Files", "PROGRAMFILES(X86)": r"C:\Program Files (x86)", "LOCALAPPDATA": r"C:\Users\me\AppData\Local"}
chrome_pf = str(Path(r"C:\Program Files") / "Google" / "Chrome" / "Application" / "chrome.exe")
edge_x86 = str(Path(r"C:\Program Files (x86)") / "Microsoft" / "Edge" / "Application" / "msedge.exe")
chrome_local = str(Path(r"C:\Users\me\AppData\Local") / "Google" / "Chrome" / "Application" / "chrome.exe")

check(find_chrome("win32", WIN_ENV, lambda p: p == chrome_pf) == chrome_pf, "windows: Chrome in Program Files")
check(find_chrome("win32", WIN_ENV, lambda p: p == chrome_local) == chrome_local, "windows: per-user Chrome in LocalAppData")
check(find_chrome("win32", WIN_ENV, lambda p: p == edge_x86) == edge_x86, "windows: falls back to Edge when Chrome is missing")
check(find_chrome("win32", WIN_ENV, lambda p: False) is None, "windows: None when no browser is installed")
check(find_chrome("win32", {**WIN_ENV, "CHROME_PATH": r"D:\b\chrome.exe"}, lambda p: p in (r"D:\b\chrome.exe", chrome_pf)) == r"D:\b\chrome.exe", "CHROME_PATH wins over the default")
check(find_chrome("win32", {**WIN_ENV, "CHROME_PATH": r"D:\gone.exe"}, lambda p: p == chrome_pf) == chrome_pf, "a stale CHROME_PATH falls through to the defaults")
check(find_chrome("darwin", {}, lambda p: p.endswith("Google Chrome")) is not None, "mac: Chrome app bundle")
check(find_chrome("linux", {}, lambda p: p == "/usr/bin/chromium", lambda n: "/usr/bin/chromium" if n == "chromium" else None) == "/usr/bin/chromium", "linux: chromium on PATH")
check(not any("Applications" in c for c in chrome_candidates("win32", WIN_ENV)), "windows candidates contain no mac paths")
check(chrome_candidates("win32", {}) == [], "windows with no environment does not crash")
check(resolve_cmd(["definitely-not-a-command-xyz", "--x"]) == ["definitely-not-a-command-xyz", "--x"], "unknown commands are left as they are")
check(resolve_cmd([sys.executable.split("/")[-1].split("\\")[-1], "-V"])[1:] == ["-V"], "arguments are preserved when resolving")

if failures:
    print(f"\n{len(failures)} check(s) failed")
    sys.exit(1)
print("\nall checks passed")
