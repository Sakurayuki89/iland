import * as Phaser from "phaser";
import { startBench } from "../lib/bench";
import { type Action, animKey, createCharacterAnims, preloadCharacter } from "../lib/character";
import { CHARACTERS } from "../lib/characters";
import { type Direction, directionFromVector } from "../lib/direction";
import { spawnWanderers } from "../lib/stress";

const SPEED = 140; // px/s, sandbox only
const CELL = 64;
const STRESS_SCALE = 0.5; // crowd sprites are drawn at half size, like a world view

/**
 * Dev-only harness for the art/tool pipeline. No game rules live here.
 *   tap/click : walk there            ?char=siamese_base : pick a texture
 *   ?dir=left&act=walk|idle|net : loop one animation (used for screenshots)
 *   ?grid=0 : hide the debug grid
 *   ?stress=N : N wandering sprites (perf test)   ?bench=SECONDS&report=URL : sample and POST frame stats
 */
export class SandboxScene extends Phaser.Scene {
  private hero!: Phaser.GameObjects.Sprite;
  private flips = new Map<string, boolean>();
  private charKey: string = CHARACTERS[0];
  private dir: Direction = "down";
  private target: Phaser.Math.Vector2 | null = null;
  private fixed = false;
  private hud!: Phaser.GameObjects.Text;
  private crowd: ((deltaMs: number) => void) | null = null;
  private stress = 0;

  constructor() {
    super("sandbox");
  }

  preload(): void {
    for (const k of CHARACTERS) preloadCharacter(this, k);
  }

  create(): void {
    const q = new URLSearchParams(location.search);
    const wanted = q.get("char") ?? "";
    this.charKey = (CHARACTERS as readonly string[]).includes(wanted) ? wanted : CHARACTERS[0];
    const flipsByKey = new Map<string, Map<string, boolean>>();
    for (const k of CHARACTERS) {
      const flips = createCharacterAnims(this, k);
      flipsByKey.set(k, flips);
      if (k === this.charKey) this.flips = flips;
    }

    const { width, height } = this.scale;
    if (q.get("grid") !== "0") this.drawGrid(width, height);

    this.hero = this.add.sprite(width / 2, height * 0.72, this.charKey, "down_idle");

    const dir = q.get("dir") as Direction | null;
    const act = q.get("act") as Action | null;
    this.stress = Math.max(0, Number(q.get("stress") ?? 0) | 0);
    if (act) {
      this.fixed = true;
      this.dir = dir ?? "down";
      this.play(act, this.dir);
    } else {
      this.play("idle", this.dir);
      this.input.on("pointerdown", (p: Phaser.Input.Pointer) => {
        this.target = new Phaser.Math.Vector2(p.worldX, p.worldY);
      });
    }
    if (this.stress > 0) this.crowd = spawnWanderers(this, this.stress, CHARACTERS, flipsByKey, STRESS_SCALE);

    this.hud = this.add.text(10, 8, "", { fontFamily: "ui-monospace, monospace", fontSize: "14px", color: "#2b2620" }).setDepth(1e9);

    const bench = Number(q.get("bench") ?? 0);
    if (bench > 0) {
      startBench(this.game, {
        seconds: bench,
        warmup: 2,
        report: q.get("report"),
        label: `stress=${this.stress}`,
        extra: () => ({ sprites: this.children.length, texture_mb: +this.textureMb().toFixed(2), canvas: `${width}x${height}` }),
      });
    }
  }

  update(_time: number, delta: number): void {
    this.hud.setText(
      `${this.charKey}  fps ${Math.round(this.game.loop.actualFps)}  objects ${this.children.length}  tex ${this.textureMb().toFixed(1)}MB` +
        (this.fixed || this.stress ? "" : "  tap to move"),
    );
    this.crowd?.(delta);
    if (this.fixed || !this.target) return;

    const dx = this.target.x - this.hero.x;
    const dy = this.target.y - this.hero.y;
    const dist = Math.hypot(dx, dy);
    const step = (SPEED * delta) / 1000;
    if (dist <= step) {
      this.hero.setPosition(this.target.x, this.target.y);
      this.target = null;
      this.play("idle", this.dir);
      return;
    }
    this.dir = directionFromVector(dx, dy, this.dir);
    this.hero.x += (dx / dist) * step;
    this.hero.y += (dy / dist) * step;
    this.hero.setDepth(this.hero.y); // feet-based depth sort (origin is the atlas pivot at the feet)
    this.play("walk", this.dir);
  }

  /** Rough GPU texture memory of the loaded character atlases (RGBA8, no mipmaps). */
  private textureMb(): number {
    let bytes = 0;
    for (const k of CHARACTERS) {
      const src = this.textures.get(k).source[0];
      if (src) bytes += src.width * src.height * 4;
    }
    return bytes / 1e6;
  }

  private play(action: Action, dir: Direction): void {
    const key = animKey(this.charKey, action, dir);
    this.hero.setFlipX(this.flips.get(key) ?? false);
    this.hero.anims.play(key, true);
  }

  private drawGrid(w: number, h: number): void {
    const g = this.add.graphics().lineStyle(1, 0x000000, 0.08);
    for (let x = 0; x <= w; x += CELL) g.lineBetween(x, 0, x, h);
    for (let y = 0; y <= h; y += CELL) g.lineBetween(0, y, w, y);
  }
}
