/**
 * Action Lab (dev only): preview and tune character actions on a timeline.
 * Timeline widget = animation-timeline-js, panels = Tweakpane, playback = the same
 * lib/action + lib/actionPlayer + lib/fx code the game uses.
 *
 * URL presets: ?action=fall&dir=left&char=siamese_base&t=0.4&play=0&speed=0.5
 * Keys: Space play/pause · ←/→ one frame (Shift = 0.1s) · Delete removes the selected key
 */
import { Timeline, TimelineEventSource, type TimelineKeyframe, type TimelineModel } from "animation-timeline-js";
import * as Phaser from "phaser";
import { type FolderApi, Pane } from "tweakpane";
import {
  ActionClock, type ActionDef, EASE_NAMES, type EventKey, FX_NAMES, type FrameKey, type Key,
  TRACK_DEFAULTS, TRACK_NAMES, type TrackName, frameAt, poseAt, sampleTrack, validateAction,
} from "../lib/action";
import { applyPose } from "../lib/actionPlayer";
import { preloadCharacter } from "../lib/character";
import { CHARACTERS, CHAR_HEIGHT } from "../lib/characters";
import type { Direction } from "../lib/direction";
import { playFx } from "../lib/fx";

const DIRECTIONS: Direction[] = ["left", "right", "down", "up"];
const API = "/__lab/actions";
const W = 640;
const H = 400;
const BASE = { x: W / 2, y: 330, scale: 1.4 };
const FRAME = 1 / 60;

type RowId = "frames" | TrackName | "events";
type AnyKey = Key | FrameKey | EventKey;
type LabKeyframe = TimelineKeyframe & { row: RowId; key: AnyKey };
const ROWS: RowId[] = ["frames", ...TRACK_NAMES, "events"];

const q = new URLSearchParams(location.search);
const st = {
  actions: [] as ActionDef[],
  id: q.get("action") ?? "walk",
  t: Number(q.get("t") ?? 0),
  playing: q.get("play") !== "0",
  speed: Number(q.get("speed") ?? 1),
  dir: (DIRECTIONS.includes(q.get("dir") as Direction) ? q.get("dir") : "left") as Direction,
  char: (CHARACTERS as readonly string[]).includes(q.get("char") ?? "") ? (q.get("char") as string) : (CHARACTERS[0] as string),
  sel: null as { row: RowId; key: AnyKey } | null,
  dirty: false,
  ground: 0,
  newId: "",
};

const $ = (id: string): HTMLElement => document.getElementById(id) as HTMLElement;
const round = (v: number, step = 0.01): number => Math.round(v / step) * step;
const cur = (): ActionDef => st.actions.find((a) => a.id === st.id) ?? (st.actions[0] as ActionDef);
const keysOf = (a: ActionDef, row: RowId): AnyKey[] => (row === "frames" ? a.frames : row === "events" ? a.events : (a.tracks[row] ?? []));
const say = (text: string, err = false): void => {
  $("msg").textContent = text;
  $("msg").className = err ? "err" : "";
};

let scene: LabScene;
let timeline: Timeline;
let left: Pane;
let right: Pane;
let keyFolder: FolderApi | null = null;
const clock = new ActionClock();
const valueCells = new Map<RowId, HTMLElement>();

class LabScene extends Phaser.Scene {
  sprite!: Phaser.GameObjects.Sprite;
  ground!: Phaser.GameObjects.Graphics;

  preload(): void {
    for (const k of CHARACTERS) preloadCharacter(this, k);
  }
  create(): void {
    this.ground = this.add.graphics();
    this.sprite = this.add.sprite(BASE.x, BASE.y, st.char, "down_idle").setDepth(BASE.y);
    scene = this;
    void boot();
  }
  update(_time: number, delta: number): void {
    if (st.actions.length) tick(delta / 1000);
  }
}

function fire(events: EventKey[]): void {
  for (const e of events) playFx(scene, e.fx, { x: BASE.x, y: BASE.y, height: CHAR_HEIGHT * BASE.scale, dir: st.dir, sprite: scene.sprite });
}

function tick(dt: number): void {
  const a = cur();
  if (st.playing) {
    // the clock owns stepping, events and hit-stop; st.t stays the single place the UI reads and seeks
    if (clock.t !== st.t) clock.reset(st.t);
    const fired = clock.step(a, dt * st.speed);
    st.t = clock.t;
    fire(fired);
    if (clock.freeze <= 0) st.ground += (a.move?.speed ?? 0) * dt * st.speed;
    if (clock.done) {
      st.playing = false;
      left.refresh();
    }
    timeline.setTime(st.t * 1000);
  }
  draw(a);
}

function draw(a: ActionDef): void {
  (window as unknown as { __labTime: number }).__labTime = st.t; // read by tools/shot.py --until
  const pose = poseAt(a, st.t);
  const ok = applyPose(scene.sprite, pose, st.dir, BASE);
  drawGround();
  $("status").textContent =
    `${a.label} · ${st.t.toFixed(3)}s / ${a.duration}s · frame ${Math.round(st.t * 60)}${st.dirty ? " · 저장 안 됨 ●" : ""}` +
    (ok ? "" : ` · ⚠ ${st.char}에 '${pose.frame}' 포즈 없음`);
  valueCells.get("frames")!.textContent = pose.frame;
  valueCells.get("events")!.textContent = `${a.events.length}개`;
  for (const name of TRACK_NAMES) valueCells.get(name)!.textContent = pose[name].toFixed(2);
}

function drawGround(): void {
  const g = scene.ground.clear();
  g.lineStyle(2, 0x000000, 0.35).lineBetween(0, BASE.y, W, BASE.y);
  const gap = 60;
  const off = ((st.ground % gap) + gap) % gap;
  g.lineStyle(2, 0x000000, 0.2);
  if (st.dir === "left" || st.dir === "right") {
    const s = st.dir === "left" ? 1 : -1; // ground slides opposite to the walk direction
    for (let x = -gap; x <= W + gap; x += gap) g.lineBetween(x + s * off, BASE.y, x + s * off, BASE.y + 14);
  } else {
    const s = st.dir === "down" ? -1 : 1;
    for (let y = -gap; y <= H + gap; y += gap) {
      g.lineBetween(W / 2 - 150, y + s * off, W / 2 - 126, y + s * off);
      g.lineBetween(W / 2 + 126, y + s * off, W / 2 + 150, y + s * off);
    }
  }
}

function seek(t: number): void {
  st.t = Math.min(Math.max(t, 0), cur().duration);
  timeline.setTime(st.t * 1000);
}

function touch(): void {
  st.dirty = true;
}

function sortKeys(a: ActionDef): void {
  const byT = (x: AnyKey, y: AnyKey): number => x.t - y.t;
  a.frames.sort(byT);
  a.events.sort(byT);
  for (const name of TRACK_NAMES) a.tracks[name]?.sort(byT);
}

function buildModel(): void {
  const a = cur();
  const model: TimelineModel = {
    rows: ROWS.map((row) => ({
      keyframes: keysOf(a, row).map(
        (key): LabKeyframe => ({ val: key.t * 1000, row, key, selected: st.sel?.key === key, draggable: !(row === "frames" && key === a.frames[0]) }),
      ),
    })),
  };
  timeline.setModel(model);
  timeline.setTime(st.t * 1000);
}

function addKey(row: RowId): void {
  const a = cur();
  const t = round(st.t);
  let key: AnyKey;
  if (row === "frames") a.frames.push((key = { t, frame: frameAt(a, t) }));
  else if (row === "events") a.events.push((key = { t, fx: "dust" }));
  else (a.tracks[row] ??= []).push((key = { t, v: round(sampleTrack(a.tracks[row], t, TRACK_DEFAULTS[row]), 0.001) }));
  sortKeys(a);
  st.sel = { row, key };
  touch();
  buildModel();
  buildKeyFolder();
}

function deleteSelected(): void {
  const a = cur();
  if (!st.sel) return;
  const { row, key } = st.sel;
  if (row === "frames" && key === a.frames[0]) return say("첫 프레임 키(t=0)는 지울 수 없습니다.", true);
  const list = keysOf(a, row);
  list.splice(list.indexOf(key), 1);
  if (row !== "frames" && row !== "events" && list.length === 0) delete a.tracks[row];
  st.sel = null;
  touch();
  buildModel();
  buildKeyFolder();
}

function poseNames(): string[] {
  return scene.textures.get(st.char).getFrameNames().filter((n) => n.startsWith("down_")).map((n) => n.slice(5));
}

const options = (names: readonly string[]): Record<string, string> => Object.fromEntries(names.map((n) => [n, n]));

function buildKeyFolder(): void {
  keyFolder?.dispose();
  keyFolder = null;
  if (!st.sel) return;
  const { row, key } = st.sel;
  const a = cur();
  const f = (keyFolder = right.addFolder({ title: `선택한 키 · ${row}` }));
  const changed = (resort: boolean) => (): void => {
    touch();
    if (resort) {
      sortKeys(a);
      buildModel();
    }
  };
  if (!(row === "frames" && key === a.frames[0])) f.addBinding(key, "t", { label: "시간(s)", min: 0, max: a.duration, step: 0.01 }).on("change", changed(true));
  if ("frame" in key) f.addBinding(key, "frame", { label: "포즈", options: options(poseNames()) }).on("change", changed(false));
  else if ("fx" in key) f.addBinding(key, "fx", { label: "효과", options: options(FX_NAMES) }).on("change", changed(false));
  else {
    f.addBinding(key, "v", { label: "값", step: 0.01 }).on("change", changed(false));
    const proxy = { ease: key.ease ?? "linear" };
    f.addBinding(proxy, "ease", { label: "이징", options: options(EASE_NAMES) }).on("change", (ev) => {
      if (ev.value === "linear") delete key.ease;
      else key.ease = ev.value;
      touch();
    });
  }
  f.addButton({ title: "이 키 삭제 (Delete)" }).on("click", deleteSelected);
}

function buildPanes(): void {
  left?.dispose();
  right?.dispose();
  keyFolder = null;
  const a = cur();

  left = new Pane({ container: $("ctl"), title: "재생" });
  left.addBinding(st, "id", { label: "액션", options: Object.fromEntries(st.actions.map((x) => [`${x.label} (${x.id})`, x.id])) }).on("change", () => {
    st.sel = null;
    st.t = 0;
    st.ground = 0;
    st.playing = true;
    configureTimeline();
    buildPanes();
  });
  left.addBinding(st, "char", { label: "캐릭터", options: options(CHARACTERS) }).on("change", () => {
    scene.sprite.setTexture(st.char, "down_idle");
    buildKeyFolder();
  });
  left.addBinding(st, "dir", { label: "방향", options: options(DIRECTIONS) });
  left.addBinding(st, "speed", { label: "배속", min: 0.1, max: 2, step: 0.05 });
  left.addBinding(st, "playing", { label: "재생 (Space)" }).on("change", (ev) => {
    if (ev.value && st.t >= cur().duration) st.t = 0;
  });
  left.addButton({ title: "⏮ 처음부터" }).on("click", () => {
    st.t = 0;
    st.playing = true;
    left.refresh();
  });
  left.addButton({ title: "◀ 한 프레임 (←)" }).on("click", () => step(-FRAME));
  left.addButton({ title: "한 프레임 ▶ (→)" }).on("click", () => step(FRAME));

  right = new Pane({ container: $("insp"), title: "액션 속성" });
  const props = { label: a.label, duration: a.duration, loop: a.loop, speed: a.move?.speed ?? 0 };
  right.addBinding(props, "label", { label: "이름" }).on("change", (ev) => {
    a.label = ev.value;
    touch();
  });
  right.addBinding(props, "duration", { label: "길이(s)", min: 0.05, max: 10, step: 0.01 }).on("change", (ev) => {
    a.duration = ev.value;
    touch();
    configureTimeline();
  });
  right.addBinding(props, "loop", { label: "반복" }).on("change", (ev) => {
    a.loop = ev.value;
    touch();
  });
  right.addBinding(props, "speed", { label: "이동 px/s", min: 0, max: 400, step: 5 }).on("change", (ev) => {
    if (ev.value > 0) a.move = { speed: ev.value };
    else delete a.move;
    touch();
  });
  right.addButton({ title: "💾 저장 (data/actions)" }).on("click", () => void save());
  right.addButton({ title: "↩ 디스크에서 다시 읽기" }).on("click", () => void reload());
  const clone = right.addFolder({ title: "새 액션으로 복제", expanded: false });
  clone.addBinding(st, "newId", { label: "새 id" });
  clone.addButton({ title: "복제" }).on("click", duplicate);
  buildKeyFolder();
}

function configureTimeline(): void {
  const dur = cur().duration * 1000;
  timeline.setOptions({ min: 0, max: Math.max(dur, 100), stepVal: dur > 3000 ? 500 : 100, stepPx: dur > 3000 ? 80 : 50, zoom: 1 });
  buildModel();
}

function step(dt: number): void {
  st.playing = false;
  left.refresh();
  seek(round(st.t + dt, FRAME));
}

function cleaned(a: ActionDef): ActionDef {
  const copy = JSON.parse(JSON.stringify(a)) as ActionDef;
  for (const name of TRACK_NAMES) if (copy.tracks[name]?.length === 0) delete copy.tracks[name];
  const r = (k: { t: number }): void => {
    k.t = +k.t.toFixed(3);
  };
  copy.frames.forEach(r);
  copy.events.forEach(r);
  for (const name of TRACK_NAMES) copy.tracks[name]?.forEach(r);
  return copy;
}

async function save(): Promise<void> {
  const a = cleaned(cur());
  const errs = validateAction(a);
  if (errs.length) return say(`저장 안 함: ${errs.join(" / ")}`, true);
  const res = await fetch(API, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(a) });
  if (!res.ok) return say(`저장 실패 (${res.status}): ${await res.text()}`, true);
  st.dirty = false;
  say(`저장됨: data/actions/${a.id}.json`);
}

async function reload(): Promise<void> {
  st.actions = (await (await fetch(API)).json()) as ActionDef[];
  if (!st.actions.some((a) => a.id === st.id)) st.id = st.actions[0]?.id ?? "";
  st.sel = null;
  st.dirty = false;
  configureTimeline();
  buildPanes();
  say(`액션 ${st.actions.length}개 불러옴`);
}

function duplicate(): void {
  const id = st.newId.trim();
  if (!/^[a-z0-9_]+$/.test(id)) return say("새 id는 영소문자·숫자·밑줄만 쓸 수 있습니다.", true);
  if (st.actions.some((a) => a.id === id)) return say(`'${id}'는 이미 있습니다.`, true);
  const copy = cleaned(cur());
  copy.id = id;
  copy.label = `${copy.label} 복사본`;
  st.actions.push(copy);
  st.id = id;
  st.sel = null;
  touch();
  configureTimeline();
  buildPanes();
  say(`'${id}' 생성 — 저장을 눌러야 파일로 남습니다.`);
}

function buildLabels(): void {
  const names: Record<RowId, string> = {
    frames: "포즈", x: "x 앞으로", lift: "lift 높이", scaleX: "scaleX", scaleY: "scaleY", rotation: "rotation 회전", lean: "lean 기울임", alpha: "alpha", events: "효과",
  };
  const root = $("labels");
  root.innerHTML = '<div class="head">트랙 · 현재 값 · 키 추가</div>';
  for (const row of ROWS) {
    const el = document.createElement("div");
    el.className = "row";
    const name = document.createElement("b");
    name.textContent = names[row];
    const val = document.createElement("span");
    const add = document.createElement("button");
    add.textContent = "+";
    add.title = "재생 위치에 키 추가";
    add.addEventListener("click", () => addKey(row));
    el.append(name, val, add);
    root.append(el);
    valueCells.set(row, val);
  }
}

function syncFromTimeline(): void {
  for (const kf of timeline.getAllKeyframes() as LabKeyframe[]) kf.key.t = Math.max(0, Math.round(kf.val) / 1000);
  touch();
}

async function boot(): Promise<void> {
  buildLabels();
  timeline = new Timeline({
    id: $("timeline"),
    headerHeight: 30,
    rowsStyle: { height: 24, marginBottom: 2 },
    snapEnabled: true,
    snapStep: 10,
    leftMargin: 14,
  });
  timeline.onTimeChanged((e) => {
    if (e.source === TimelineEventSource.SetTimeMethod) return;
    st.playing = false;
    st.t = Math.min(Math.max(e.val / 1000, 0), cur().duration);
    left.refresh();
  });
  timeline.onKeyframeChanged(syncFromTimeline);
  timeline.onDragFinished(() => {
    syncFromTimeline();
    sortKeys(cur());
    buildModel();
    right.refresh();
  });
  timeline.onSelected((e) => {
    const kf = e.selected[0] as LabKeyframe | undefined;
    st.sel = kf ? { row: kf.row, key: kf.key } : null;
    buildKeyFolder();
  });

  window.addEventListener("keydown", (ev) => {
    const tag = (ev.target as HTMLElement).tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    if (ev.code === "Space") {
      st.playing = !st.playing;
      if (st.playing && st.t >= cur().duration) st.t = 0;
      left.refresh();
    } else if (ev.code === "ArrowLeft") step(ev.shiftKey ? -0.1 : -FRAME);
    else if (ev.code === "ArrowRight") step(ev.shiftKey ? 0.1 : FRAME);
    else if (ev.code === "Delete" || ev.code === "Backspace") deleteSelected();
    else return;
    ev.preventDefault();
  });
  window.addEventListener("beforeunload", (ev) => {
    if (st.dirty) ev.preventDefault();
  });

  const t0 = st.t;
  await reload();
  seek(t0);
}

new Phaser.Game({
  type: Phaser.AUTO,
  parent: "game",
  width: W,
  height: H,
  backgroundColor: "#b9d98a",
  scene: [LabScene],
});
