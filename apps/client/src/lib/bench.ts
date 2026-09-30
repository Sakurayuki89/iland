import * as Phaser from "phaser";

export interface BenchOptions {
  seconds: number;
  warmup: number;
  report: string | null;
  label: string;
  extra: () => Record<string, unknown>;
}

const pct = (sorted: number[], p: number): number => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))] ?? 0;
const mean = (a: number[]): number => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0);

function gpuName(): string {
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    const ext = gl?.getExtension("WEBGL_debug_renderer_info");
    return gl && ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : "unknown";
  } catch {
    return "unknown";
  }
}

/** Samples frame intervals + CPU time for update/render, then POSTs a JSON summary to `report`. */
export function startBench(game: Phaser.Game, o: BenchOptions): void {
  const E = Phaser.Core.Events;
  const t0 = performance.now();
  const intervals: number[] = [];
  const updMs: number[] = [];
  const renMs: number[] = [];
  let stepAt = 0;
  let renderAt = 0;
  let lastPost = 0;
  let done = false;
  const measuring = () => performance.now() - t0 >= o.warmup * 1000;

  game.events.on(E.PRE_STEP, () => { stepAt = performance.now(); });
  game.events.on(E.POST_STEP, () => { if (measuring()) updMs.push(performance.now() - stepAt); });
  game.events.on(E.PRE_RENDER, () => { renderAt = performance.now(); });
  game.events.on(E.POST_RENDER, () => {
    const now = performance.now();
    if (measuring()) {
      renMs.push(now - renderAt);
      if (lastPost) intervals.push(now - lastPost);
    }
    lastPost = now;
    if (!done && now - t0 >= (o.warmup + o.seconds) * 1000) {
      done = true;
      const s = [...intervals].sort((a, b) => a - b);
      const result = {
        label: o.label,
        frames: intervals.length,
        fps: +(1000 / mean(intervals)).toFixed(1),
        frame_ms_avg: +mean(intervals).toFixed(2),
        frame_ms_p95: +pct(s, 0.95).toFixed(2),
        frame_ms_max: +(s[s.length - 1] ?? 0).toFixed(2),
        update_ms_avg: +mean(updMs).toFixed(3),
        render_cpu_ms_avg: +mean(renMs).toFixed(3),
        gpu: gpuName(),
        ...o.extra(),
      };
      console.log("BENCH " + JSON.stringify(result));
      if (o.report) void fetch(o.report, { method: "POST", body: JSON.stringify(result) }).catch(() => undefined);
    }
  });
}
