/**
 * Data-driven character actions (run, sneak, fall, surprise ...).
 * Pure logic, no Phaser: the lab, the game and tests all share it.
 *
 * An action reuses the existing atlas poses and layers keyframed transforms and FX on top,
 * so new actions cost no extra texture memory.
 */

export const TRACK_NAMES = ["x", "lift", "scaleX", "scaleY", "rotation", "lean", "alpha"] as const;
export type TrackName = (typeof TRACK_NAMES)[number];

/**
 * x: px forward (facing direction) · lift: px above the ground · scaleX/scaleY: squash & stretch
 * rotation: degrees, mirrored when facing left · lean: degrees forward, side-facing only · alpha: 0..1
 * px are in source-frame pixels (multiplied by the sprite's base scale).
 */
export const TRACK_DEFAULTS: Record<TrackName, number> = { x: 0, lift: 0, scaleX: 1, scaleY: 1, rotation: 0, lean: 0, alpha: 1 };

export const EASE_NAMES = ["linear", "step", "sineIn", "sineOut", "sineInOut", "quadIn", "quadOut", "backOut", "bounceOut"] as const;
export type EaseName = (typeof EASE_NAMES)[number];

export const FX_NAMES = ["dust", "exclaim", "question", "stars", "sweat", "sparkle", "heart", "shake", "swoosh", "impact", "ghost", "hitstop"] as const;
export type FxName = (typeof FX_NAMES)[number];

/** `ease` shapes the move INTO this key from the previous one. */
export interface Key { t: number; v: number; ease?: EaseName }
/** `frame` is a pose name without direction, e.g. "idle", "walk_a", "net". */
export interface FrameKey { t: number; frame: string }
export interface EventKey { t: number; fx: FxName }

export interface ActionDef {
  id: string;
  label: string;
  duration: number;
  loop: boolean;
  frames: FrameKey[];
  tracks: Partial<Record<TrackName, Key[]>>;
  events: EventKey[];
  /** Travel speed in px/s while this action plays (lab: ground scroll, to check foot sliding). */
  move?: { speed: number };
}

export type Pose = Record<TrackName, number> & { frame: string };

const bounceOut = (u: number): number => {
  const n = 7.5625;
  const d = 2.75;
  if (u < 1 / d) return n * u * u;
  if (u < 2 / d) return n * (u -= 1.5 / d) * u + 0.75;
  if (u < 2.5 / d) return n * (u -= 2.25 / d) * u + 0.9375;
  return n * (u -= 2.625 / d) * u + 0.984375;
};

export const EASES: Record<EaseName, (u: number) => number> = {
  linear: (u) => u,
  step: (u) => (u >= 1 ? 1 : 0),
  sineIn: (u) => 1 - Math.cos((u * Math.PI) / 2),
  sineOut: (u) => Math.sin((u * Math.PI) / 2),
  sineInOut: (u) => -(Math.cos(Math.PI * u) - 1) / 2,
  quadIn: (u) => u * u,
  quadOut: (u) => 1 - (1 - u) * (1 - u),
  backOut: (u) => 1 + 2.70158 * (u - 1) ** 3 + 1.70158 * (u - 1) ** 2,
  bounceOut,
};

export function sampleTrack(keys: readonly Key[] | undefined, t: number, fallback: number): number {
  if (!keys || keys.length === 0) return fallback;
  const first = keys[0]!;
  if (t <= first.t) return first.v;
  for (let i = 1; i < keys.length; i++) {
    const b = keys[i]!;
    if (t < b.t) {
      const a = keys[i - 1]!;
      const u = (t - a.t) / (b.t - a.t);
      return a.v + (b.v - a.v) * EASES[b.ease ?? "linear"](u);
    }
  }
  return keys[keys.length - 1]!.v;
}

export function frameAt(action: ActionDef, t: number): string {
  let name = action.frames[0]?.frame ?? "idle";
  for (const f of action.frames) {
    if (f.t <= t) name = f.frame;
    else break;
  }
  return name;
}

export function poseAt(action: ActionDef, t: number): Pose {
  const tt = Math.min(Math.max(t, 0), action.duration);
  const pose = { frame: frameAt(action, tt) } as Pose;
  for (const name of TRACK_NAMES) pose[name] = sampleTrack(action.tracks[name], tt, TRACK_DEFAULTS[name]);
  return pose;
}

/** Events with from <= t < to. For a loop wrap call it twice: [prev, duration + eps) then [0, next). */
export function eventsBetween(action: ActionDef, from: number, to: number): EventKey[] {
  return action.events.filter((e) => e.t >= from && e.t < to);
}

/** How long a "hitstop" event freezes the action (seconds). The short pause on contact is what sells an impact. */
export const HITSTOP_SECONDS = 0.08;

/** Playback position of one action. Shared by the lab and the game so timing, events and hit-stop match. */
export class ActionClock {
  t = 0;
  /** Remaining hit-stop time; while > 0 the action does not advance. */
  freeze = 0;
  /** True once a non-looping action has reached its end. */
  done = false;

  reset(t = 0): void {
    this.t = t;
    this.freeze = 0;
    this.done = false;
  }

  /** Advance by dt seconds (already speed-scaled) and return the events crossed, each exactly once. */
  step(action: ActionDef, dt: number): EventKey[] {
    if (this.done) return [];
    if (this.freeze > 0) {
      const used = Math.min(this.freeze, dt);
      this.freeze -= used;
      dt -= used;
      if (dt <= 0) return [];
    }
    const prev = this.t;
    let next = prev + dt;
    let fired: EventKey[];
    if (next >= action.duration) {
      fired = eventsBetween(action, prev, action.duration + 1e-9);
      if (action.loop) {
        next %= action.duration;
        fired = fired.concat(eventsBetween(action, 0, next));
      } else {
        next = action.duration;
        this.done = true;
      }
    } else fired = eventsBetween(action, prev, next);
    this.t = next;
    if (fired.some((e) => e.fx === "hitstop")) this.freeze = HITSTOP_SECONDS;
    return fired;
  }
}

const isObj = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);
const isNum = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x);

/** Returns a list of problems (empty = valid). */
export function validateAction(x: unknown): string[] {
  const errs: string[] = [];
  if (!isObj(x)) return ["action must be an object"];
  if (typeof x.id !== "string" || !/^[a-z0-9_]+$/.test(x.id)) errs.push("id must match [a-z0-9_]+");
  if (typeof x.label !== "string" || !x.label) errs.push("label is required");
  if (typeof x.loop !== "boolean") errs.push("loop must be true/false");
  const dur = x.duration;
  if (!isNum(dur) || dur <= 0 || dur > 10) {
    errs.push("duration must be in (0, 10] seconds");
    return errs;
  }

  const ordered = (name: string, list: unknown, check: (k: Record<string, unknown>, where: string) => void): void => {
    if (!Array.isArray(list)) {
      errs.push(`${name} must be a list`);
      return;
    }
    let prev = -Infinity;
    list.forEach((k, i) => {
      const where = `${name}[${i}]`;
      if (!isObj(k) || !isNum(k.t)) {
        errs.push(`${where}: t must be a number`);
        return;
      }
      if (k.t < 0 || k.t > dur) errs.push(`${where}: t=${k.t} is outside 0..${dur}`);
      if (k.t < prev) errs.push(`${where}: keys must be sorted by t`);
      prev = k.t;
      check(k, where);
    });
  };

  ordered("frames", x.frames, (k, where) => {
    if (typeof k.frame !== "string" || !k.frame) errs.push(`${where}: frame name is required`);
  });
  if (Array.isArray(x.frames)) {
    const first = x.frames[0] as unknown;
    if (!isObj(first)) errs.push("frames needs at least one key");
    else if (first.t !== 0) errs.push("frames[0] must start at t=0");
  }

  if (!isObj(x.tracks)) errs.push("tracks must be an object");
  else {
    for (const [name, keys] of Object.entries(x.tracks)) {
      if (!(TRACK_NAMES as readonly string[]).includes(name)) {
        errs.push(`tracks.${name}: unknown track`);
        continue;
      }
      ordered(`tracks.${name}`, keys, (k, where) => {
        if (!isNum(k.v)) errs.push(`${where}: v must be a number`);
        if (k.ease !== undefined && !(EASE_NAMES as readonly unknown[]).includes(k.ease)) errs.push(`${where}: unknown ease "${String(k.ease)}"`);
      });
    }
  }

  ordered("events", x.events, (k, where) => {
    if (!(FX_NAMES as readonly unknown[]).includes(k.fx)) errs.push(`${where}: unknown fx "${String(k.fx)}"`);
  });

  if (x.move !== undefined && (!isObj(x.move) || !isNum(x.move.speed) || x.move.speed < 0)) errs.push("move.speed must be >= 0");
  return errs;
}
