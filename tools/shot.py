#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["websockets"]
# ///
"""Screenshot a page after it has run for N real seconds (headless Chrome over CDP).

`chrome --screenshot` captures at load (or in virtual time, where game loops barely advance),
so animations and effects never show. This waits in real time, then captures.

  uv run tools/shot.py "http://127.0.0.1:5173/lab.html?action=run" out.png --wait 1.2
  uv run tools/shot.py URL out.png --wait 0.5 --frames 4 --every 0.12   # out_0.png .. out_3.png
  uv run tools/shot.py URL out.png --until "window.__labTime >= 0.26"    # wait for a page condition
"""
from __future__ import annotations

import argparse
import base64
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

from _common import CHROME_HELP, find_chrome, kill_tree, spawn, utf8_output


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--wait", type=float, default=1.0, help="real seconds to wait after load")
    ap.add_argument("--frames", type=int, default=1)
    ap.add_argument("--every", type=float, default=0.1, help="seconds between frames")
    ap.add_argument("--size", default="1280,860")
    ap.add_argument("--clip", default="", help="x,y,w,h in CSS px")
    ap.add_argument("--until", default="", help="JS expression; after --wait, keep polling until it is true (max 15s), then capture")
    a = ap.parse_args()
    utf8_output()

    chrome_exe = find_chrome()
    if not chrome_exe:
        print(CHROME_HELP, file=sys.stderr)
        return 2
    port = free_port()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as prof:  # Windows may still hold files briefly
        chrome = spawn(
            [chrome_exe, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={prof}", f"--window-size={a.size}",
             "--hide-scrollbars", "--no-first-run", "--remote-allow-origins=*", "--force-prefers-color-scheme=light", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            ws_url = None
            for _ in range(50):
                try:
                    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1))
                    ws_url = next(t["webSocketDebuggerUrl"] for t in targets if t["type"] == "page")
                    break
                except Exception:
                    time.sleep(0.1)
            if not ws_url:
                print("could not reach Chrome", file=sys.stderr)
                return 1
            with connect(ws_url, max_size=64 * 1024 * 1024) as ws:
                n = 0

                def call(method: str, **params):
                    nonlocal n
                    n += 1
                    ws.send(json.dumps({"id": n, "method": method, "params": params}))
                    while True:
                        msg = json.loads(ws.recv())
                        if msg.get("id") == n:
                            return msg.get("result", {})

                call("Page.enable")
                call("Page.navigate", url=a.url)
                time.sleep(a.wait)
                if a.until:
                    deadline = time.time() + 15
                    while time.time() < deadline:
                        r = call("Runtime.evaluate", expression=f"!!({a.until})", returnByValue=True)
                        if r.get("result", {}).get("value") is True:
                            break
                        time.sleep(0.004)
                    else:
                        print(f"warning: --until never became true: {a.until}", file=sys.stderr)
                shot = {"format": "png"}
                if a.clip:
                    x, y, w, h = (float(v) for v in a.clip.split(","))
                    shot["clip"] = {"x": x, "y": y, "width": w, "height": h, "scale": 1}
                out = Path(a.out)
                for i in range(a.frames):
                    data = call("Page.captureScreenshot", **shot)["data"]
                    path = out if a.frames == 1 else out.with_name(f"{out.stem}_{i}{out.suffix}")
                    path.write_bytes(base64.b64decode(data))
                    print(path)
                    if i + 1 < a.frames:
                        time.sleep(a.every)
        finally:
            kill_tree(chrome)
    return 0


if __name__ == "__main__":
    sys.exit(main())
