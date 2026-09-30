"""Cross-platform helpers shared by tools/*.py (macOS, Windows, Linux). No third-party imports."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"


def utf8_output() -> None:
    """Print Korean/any text without crashing on legacy consoles (cp949/cp1252 on Windows)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def which(cmd: str) -> str | None:
    """Full path of a command. On Windows this finds pnpm.cmd / npm.cmd, which a bare name cannot launch."""
    return shutil.which(cmd)


def resolve_cmd(cmd: list[str]) -> list[str]:
    """Replace the program name with its full path when found, so .cmd shims run on Windows."""
    exe = which(cmd[0])
    return [exe, *cmd[1:]] if exe else cmd


def run_text(cmd: list[str], timeout: float = 15, **kw) -> subprocess.CompletedProcess:
    """subprocess.run that decodes output as UTF-8 regardless of the system code page."""
    return subprocess.run(resolve_cmd(cmd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, **kw)


def spawn(cmd: list[str], **kw) -> subprocess.Popen:
    """Popen in its own process group / session so kill_tree can stop it with all its children."""
    if IS_WINDOWS:
        kw.setdefault("creationflags", subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        kw.setdefault("start_new_session", True)
    return subprocess.Popen(resolve_cmd(cmd), **kw)


def kill_tree(proc: subprocess.Popen, timeout: float = 5) -> None:
    """Stop a process and everything it started (vite under pnpm, Chrome helpers)."""
    if proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            import signal

            os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()


def chrome_candidates(platform: str, env: Mapping[str, str], which_fn: Callable[[str], str | None] = shutil.which) -> list[str]:
    """Places a Chromium-based browser may live, best first. Pure function so it can be tested anywhere."""
    out: list[str] = []
    if env.get("CHROME_PATH"):
        out.append(env["CHROME_PATH"])
    if platform == "darwin":
        out += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif platform.startswith("win"):
        roots = [env.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        for root in filter(None, roots):
            out += [
                str(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"),
                str(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
            ]
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
            found = which_fn(name)
            if found:
                out.append(found)
    return out


def find_chrome(
    platform: str = sys.platform,
    env: Mapping[str, str] = os.environ,
    exists: Callable[[str], bool] = os.path.exists,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> str | None:
    """Chrome, or Edge/Chromium as a fallback (same flags and DevTools protocol). Override with CHROME_PATH."""
    for cand in chrome_candidates(platform, env, which_fn):
        if exists(cand):
            return cand
    return None


CHROME_HELP = "Chrome/Edge not found. Install Chrome (Windows: winget install Google.Chrome) or set CHROME_PATH to the browser executable."
