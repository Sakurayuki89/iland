#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Crowd performance benchmark for the client (production build, headless Chrome, real time).

For each crowd size N it opens  /?stress=N&bench=SECONDS  , lets the page sample frame
intervals and CPU time for update/render, and prints a table.

How to read it:
  * Frame rate limiting and vsync are disabled, so `fps` shows HEADROOM (how fast the
    frame loop *could* run), not the 60 Hz cap you would see on a phone.
  * This measures your Mac, not a phone. Use it to compare builds and to see how cost
    scales with N; always confirm on a real low-end device before trusting absolute numbers.
  * `--software` forces Chrome's software GL (SwiftShader) = a pessimistic GPU stand-in.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RESULTS: list[dict] = []


class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            RESULTS.append(json.loads(body))
        except json.JSONDecodeError:
            pass
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def log_message(self, *a):  # silence
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stress", default="7,30,100,300", help="comma-separated crowd sizes")
    ap.add_argument("--seconds", type=int, default=6, help="sampling time per run")
    ap.add_argument("--software", action="store_true", help="force software GL (SwiftShader)")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--json", action="store_true", help="print raw JSON instead of a table")
    a = ap.parse_args()

    if not Path(CHROME).exists():
        print("Google Chrome not found; install it or edit CHROME in tools/bench.py", file=sys.stderr)
        return 2
    if not a.no_build:
        print("building client ...", flush=True)
        if subprocess.run(["pnpm", "--filter", "@island/client", "build"], cwd=ROOT, capture_output=True).returncode:
            print("build failed (run `pnpm build` to see why)", file=sys.stderr)
            return 1

    results: list[dict] = []
    srv = HTTPServer(("127.0.0.1", 8766), Receiver)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    preview = subprocess.Popen(
        ["pnpm", "--filter", "@island/client", "exec", "vite", "preview", "--port", "4173", "--strictPort", "--host", "127.0.0.1"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2.5)
    try:
        for n in [int(x) for x in a.stress.split(",")]:
            RESULTS.clear()
            url = f"http://127.0.0.1:4173/?stress={n}&bench={a.seconds}&report=http://127.0.0.1:8766/r&grid=0"
            with tempfile.TemporaryDirectory() as prof:
                flags = [
                    "--headless=new", f"--user-data-dir={prof}", "--window-size=960,540", "--hide-scrollbars",
                    "--disable-frame-rate-limit", "--disable-gpu-vsync",
                    "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                    "--disable-backgrounding-occluded-windows", "--no-first-run",
                ]
                if a.software:
                    flags += ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
                chrome = subprocess.Popen([CHROME, *flags, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                deadline = time.time() + a.seconds + 25
                while not RESULTS and time.time() < deadline:
                    time.sleep(0.25)
                chrome.terminate()
                try:
                    chrome.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    chrome.kill()
            if not RESULTS:
                print(f"N={n}: no result (timeout)", file=sys.stderr)
                continue
            results.append(RESULTS[-1])
    finally:
        preview.terminate()
        srv.shutdown()

    if a.json:
        print(json.dumps(results, indent=2))
        return 0
    print(f"\nGPU: {results[0]['gpu'] if results else '?'}    canvas {results[0].get('canvas') if results else '?'}    sample {a.seconds}s")
    print(f"{'crowd':>6} {'objects':>8} {'fps(uncapped)':>14} {'frame ms avg':>13} {'p95':>7} {'max':>7} {'update ms':>10} {'render cpu ms':>14} {'tex MB':>7}")
    for r in results:
        n = r["label"].split("=")[1]
        print(f"{n:>6} {r['sprites']:>8} {r['fps']:>14} {r['frame_ms_avg']:>13} {r['frame_ms_p95']:>7} {r['frame_ms_max']:>7} "
              f"{r['update_ms_avg']:>10} {r['render_cpu_ms_avg']:>14} {r['texture_mb']:>7}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
