import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { ActionClock, type ActionDef, HITSTOP_SECONDS, eventsBetween, frameAt, poseAt, sampleTrack, validateAction } from "./action";
import { CHARACTERS } from "./characters";

const base: ActionDef = {
  id: "t",
  label: "test",
  duration: 1,
  loop: true,
  frames: [{ t: 0, frame: "idle" }, { t: 0.5, frame: "walk_a" }],
  tracks: { lift: [{ t: 0, v: 0 }, { t: 0.5, v: 10 }, { t: 1, v: 0, ease: "step" }] },
  events: [{ t: 0, fx: "dust" }, { t: 0.5, fx: "stars" }, { t: 1, fx: "shake" }],
};

describe("sampleTrack", () => {
  it("falls back when the track is empty", () => {
    expect(sampleTrack(undefined, 0.3, 1)).toBe(1);
    expect(sampleTrack([], 0.3, 7)).toBe(7);
  });
  it("interpolates linearly and clamps at both ends", () => {
    const k = base.tracks.lift!;
    expect(sampleTrack(k, -1, 0)).toBe(0);
    expect(sampleTrack(k, 0.25, 0)).toBeCloseTo(5);
    expect(sampleTrack(k, 0.5, 0)).toBe(10);
    expect(sampleTrack(k, 5, 0)).toBe(0);
  });
  it("holds the previous value for a step key until the key time", () => {
    const k = base.tracks.lift!;
    expect(sampleTrack(k, 0.99, 0)).toBe(10);
    expect(sampleTrack(k, 1, 0)).toBe(0);
  });
  it("overshoots with backOut but lands exactly on the key", () => {
    const k = [{ t: 0, v: 0 }, { t: 1, v: 1, ease: "backOut" as const }];
    expect(sampleTrack(k, 0.6, 0)).toBeGreaterThan(1);
    expect(sampleTrack(k, 1, 0)).toBe(1);
  });
});

describe("frames and pose", () => {
  it("uses the last frame key at or before t", () => {
    expect(frameAt(base, 0)).toBe("idle");
    expect(frameAt(base, 0.49)).toBe("idle");
    expect(frameAt(base, 0.5)).toBe("walk_a");
  });
  it("fills defaults for tracks that are not authored", () => {
    const p = poseAt(base, 0.25);
    expect(p.scaleX).toBe(1);
    expect(p.alpha).toBe(1);
    expect(p.lift).toBeCloseTo(5);
  });
});

describe("eventsBetween", () => {
  it("includes the start and excludes the end", () => {
    expect(eventsBetween(base, 0, 0.5).map((e) => e.fx)).toEqual(["dust"]);
    expect(eventsBetween(base, 0.5, 1).map((e) => e.fx)).toEqual(["stars"]);
  });
  it("fires every event exactly once across a loop wrap", () => {
    const fired = [...eventsBetween(base, 0.9, base.duration + 1e-9), ...eventsBetween(base, 0, 0.1)];
    expect(fired.map((e) => e.fx)).toEqual(["shake", "dust"]);
  });
});

describe("ActionClock", () => {
  const once: ActionDef = { ...base, loop: false, events: [{ t: 0, fx: "dust" }, { t: 0.5, fx: "hitstop" }, { t: 0.5, fx: "impact" }, { t: 1, fx: "shake" }] };

  it("fires every event exactly once in small steps and stops at the end", () => {
    const c = new ActionClock();
    const fired: string[] = [];
    for (let i = 0; i < 200; i++) fired.push(...c.step(once, 1 / 60).map((e) => e.fx));
    expect(fired).toEqual(["dust", "hitstop", "impact", "shake"]);
    expect(c.done).toBe(true);
    expect(c.t).toBe(1);
  });
  it("holds time still for the hit-stop, then resumes", () => {
    const c = new ActionClock();
    c.step(once, 0.51);
    const at = c.t;
    expect(c.freeze).toBe(HITSTOP_SECONDS);
    c.step(once, HITSTOP_SECONDS / 2);
    expect(c.t).toBe(at);
    c.step(once, HITSTOP_SECONDS / 2 + 0.1);
    expect(c.t).toBeCloseTo(at + 0.1);
  });
  it("wraps a looping action and keeps going", () => {
    const c = new ActionClock();
    const fired: string[] = [];
    for (let i = 0; i < 90; i++) fired.push(...c.step(base, 1 / 60).map((e) => e.fx));
    expect(c.done).toBe(false);
    expect(fired.filter((f) => f === "stars").length).toBe(2);
  });
});

describe("validateAction", () => {
  it("accepts a well-formed action", () => {
    expect(validateAction(base)).toEqual([]);
  });
  it("reports each kind of mistake", () => {
    const bad = {
      id: "Bad Id",
      label: "",
      duration: 1,
      loop: true,
      frames: [{ t: 0.2, frame: "idle" }],
      tracks: { wobble: [], lift: [{ t: 0.5, v: 1 }, { t: 0.1, v: 2, ease: "nope" }, { t: 3, v: 0 }] },
      events: [{ t: 0.1, fx: "confetti" }],
      move: { speed: -1 },
    };
    const errs = validateAction(bad).join("\n");
    for (const needle of ["id must match", "label is required", "frames[0] must start at t=0", "unknown track", "sorted by t", 'unknown ease "nope"', "outside 0..1", 'unknown fx "confetti"', "move.speed"]) {
      expect(errs).toContain(needle);
    }
  });
  it("rejects a non-positive duration", () => {
    expect(validateAction({ ...base, duration: 0 })).toContain("duration must be in (0, 10] seconds");
  });
});

describe("data/actions/*.json", () => {
  const dir = fileURLToPath(new URL("../../../../data/actions/", import.meta.url));
  const sprites = fileURLToPath(new URL("../../../../assets/sprites/", import.meta.url));
  const files = readdirSync(dir).filter((f) => f.endsWith(".json"));
  const atlases = CHARACTERS.map((k) => ({
    k,
    frames: Object.keys((JSON.parse(readFileSync(`${sprites}${k}.json`, "utf8")) as { frames: Record<string, unknown> }).frames),
  }));

  it("has action files", () => {
    expect(files.length).toBeGreaterThan(0);
  });
  it.each(files)("%s is valid, named after its id, and only uses poses every character has", (file) => {
    const a = JSON.parse(readFileSync(dir + file, "utf8")) as ActionDef;
    expect(validateAction(a)).toEqual([]);
    expect(`${a.id}.json`).toBe(file);
    for (const { k, frames } of atlases) {
      for (const f of a.frames) {
        for (const d of ["down", "up", "left"]) expect(frames, `${k} is missing ${d}_${f.frame}`).toContain(`${d}_${f.frame}`);
      }
    }
  });
});
