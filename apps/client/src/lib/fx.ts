import * as Phaser from "phaser";
import type { FxName } from "./action";
import type { Direction } from "./direction";

export interface FxAt {
  /** feet position */
  x: number;
  y: number;
  /** on-screen character height in px */
  height: number;
  dir: Direction;
  /** the character sprite, needed by effects that copy it (afterimage) */
  sprite?: Phaser.GameObjects.Sprite;
}

const DEPTH = 1e8;
const BACK: Record<Direction, readonly [number, number]> = { left: [1, 0], right: [-1, 0], down: [0, -1], up: [0, 1] };

/** Where the net hoop lands in the drawn strike pose, measured from the atlas (in character heights from the feet). */
const STRIKE: Record<Direction, readonly [number, number]> = { left: [-0.59, -0.05], right: [0.59, -0.05], down: [-0.28, -0.06], up: [0.12, -0.9] };

function strikePoint(at: FxAt): { x: number; y: number } {
  const [dx, dy] = STRIKE[at.dir];
  return { x: at.x + dx * at.height, y: at.y + dy * at.height };
}

/** Swing trail per direction: arc centre (in character heights from the feet), sweep in degrees, and x squash. */
const SWING: Record<Direction, { cx: number; cy: number; from: number; to: number; ccw: boolean; sx: number }> = {
  right: { cx: 0, cy: -0.42, from: -125, to: 30, ccw: false, sx: 1 },
  left: { cx: 0, cy: -0.42, from: -55, to: 150, ccw: true, sx: 1 },
  down: { cx: 0.02, cy: -0.5, from: -70, to: 150, ccw: false, sx: 0.62 },
  up: { cx: 0.1, cy: -0.55, from: -15, to: -120, ccw: true, sx: 0.8 },
};

function popText(scene: Phaser.Scene, at: FxAt, glyph: string, color: string): void {
  const s = at.height / 270;
  const t = scene.add
    .text(at.x + at.height * 0.28, at.y - at.height * 0.98, glyph, { fontFamily: "system-ui, sans-serif", fontSize: "56px", fontStyle: "bold", color, stroke: "#ffffff", strokeThickness: 8 })
    .setOrigin(0.5, 1)
    .setDepth(DEPTH)
    .setScale(0);
  scene.tweens.add({ targets: t, scale: s, duration: 160, ease: "Back.easeOut" });
  scene.tweens.add({ targets: t, alpha: 0, y: t.y - 14 * s, delay: 520, duration: 220, onComplete: () => t.destroy() });
}

/** Placeholder effects drawn in code (no art yet). Each one cleans itself up. */
const FX: Record<FxName, (scene: Phaser.Scene, at: FxAt) => void> = {
  dust(scene, at) {
    const [bx, by] = BACK[at.dir];
    const u = at.height / 270;
    for (let i = 0; i < 3; i++) {
      const c = scene.add.circle(at.x + bx * 14 * u + (i - 1) * 9 * u, at.y - 4 * u + by * 8 * u, 7 * u, 0xf5efdc, 0.9).setDepth(at.y - 1);
      scene.tweens.add({
        targets: c,
        x: c.x + bx * (22 + i * 10) * u,
        y: c.y - (10 + i * 6) * u,
        scale: 2.2,
        alpha: 0,
        duration: 380 + i * 60,
        ease: "Quad.easeOut",
        onComplete: () => c.destroy(),
      });
    }
  },
  exclaim: (scene, at) => popText(scene, at, "!", "#e8543a"),
  question: (scene, at) => popText(scene, at, "?", "#3a7be8"),
  heart: (scene, at) => popText(scene, at, "♥", "#ef6f9a"),
  stars(scene, at) {
    const u = at.height / 270;
    const stars = [0, 1, 2].map(() => scene.add.star(at.x, at.y, 5, 5 * u, 11 * u, 0xffd23f).setStrokeStyle(2, 0xb8860b).setDepth(DEPTH));
    scene.tweens.addCounter({
      from: 0,
      to: 1,
      duration: 900,
      onUpdate: (tw) => {
        const v = tw.getValue() ?? 0;
        stars.forEach((s, i) => {
          const a = v * Math.PI * 4 + (i * Math.PI * 2) / 3;
          s.setPosition(at.x + Math.cos(a) * 46 * u, at.y - at.height * 0.62 + Math.sin(a) * 14 * u);
          s.setAlpha(v > 0.8 ? (1 - v) * 5 : 1);
          s.setAngle(v * 360);
        });
      },
      onComplete: () => stars.forEach((s) => s.destroy()),
    });
  },
  sweat(scene, at) {
    const u = at.height / 270;
    for (let i = 0; i < 2; i++) {
      const side = i === 0 ? -1 : 1;
      const d = scene.add.ellipse(at.x + side * at.height * 0.2, at.y - at.height * 0.85, 9 * u, 14 * u, 0x7ec8f2).setStrokeStyle(2, 0x3a8fc4).setDepth(DEPTH);
      scene.tweens.add({ targets: d, x: d.x + side * 34 * u, duration: 420, ease: "Linear" });
      scene.tweens.add({ targets: d, y: d.y + 30 * u, alpha: 0, duration: 420, ease: "Quad.easeIn", onComplete: () => d.destroy() });
    }
  },
  sparkle(scene, at) {
    const u = at.height / 270;
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * Math.PI * 2 + 0.4;
      const s = scene.add
        .star(at.x + Math.cos(a) * at.height * 0.34, at.y - at.height * 0.5 + Math.sin(a) * at.height * 0.34, 4, 3 * u, 10 * u, 0xfff2a8)
        .setStrokeStyle(1.5, 0xe0b000)
        .setDepth(DEPTH)
        .setScale(0);
      scene.tweens.add({ targets: s, scale: 1.2, angle: 90, duration: 200, delay: i * 40, ease: "Back.easeOut" });
      scene.tweens.add({ targets: s, alpha: 0, scale: 0.4, delay: 260 + i * 40, duration: 240, onComplete: () => s.destroy() });
    }
  },
  shake(scene) {
    scene.cameras.main.shake(140, 0.007);
  },
  /** Crescent trail of the swing, from the raised net to where it lands. */
  swoosh(scene, at) {
    const u = at.height / 270;
    const w = SWING[at.dir];
    const r = at.height * 0.64;
    const g = scene.add.graphics().setPosition(at.x + w.cx * at.height, at.y + w.cy * at.height).setScale(w.sx, 1).setDepth(DEPTH);
    const from = Phaser.Math.DegToRad(w.from);
    const to = Phaser.Math.DegToRad(w.to);
    const layers: [number, number, number, number][] = [[r, 20 * u, 0xffffff, 0.95], [r - 12 * u, 12 * u, 0xfff6c9, 0.75], [r - 21 * u, 6 * u, 0xffffff, 0.45]];
    for (const [rad, width, color, alpha] of layers) {
      g.lineStyle(width, color, alpha);
      g.beginPath();
      g.arc(0, 0, rad, from, to, w.ccw);
      g.strokePath();
    }
    scene.tweens.add({ targets: g, alpha: 0, angle: w.ccw ? -22 : 22, duration: 190, ease: "Quad.easeOut", onComplete: () => g.destroy() });
  },
  /** Contact burst where the net lands: flash, expanding ring and radial streaks. */
  impact(scene, at) {
    const u = at.height / 270;
    const p = strikePoint(at);
    const flash = scene.add.circle(p.x, p.y, 30 * u, 0xffffff, 1).setDepth(DEPTH);
    scene.tweens.add({ targets: flash, alpha: 0, scale: 1.7, duration: 130, onComplete: () => flash.destroy() });
    const ring = scene.add.ellipse(p.x, p.y, 56 * u, 26 * u).setStrokeStyle(7 * u, 0xffffff, 1).setDepth(DEPTH);
    scene.tweens.add({ targets: ring, scaleX: 3.2, scaleY: 3.2, alpha: 0, duration: 280, ease: "Quad.easeOut", onComplete: () => ring.destroy() });
    for (let i = 0; i < 9; i++) {
      const a = Math.PI + (i / 8) * Math.PI; // upper half only: the ground is below
      const streak = scene.add.rectangle(p.x + Math.cos(a) * 22 * u, p.y + Math.sin(a) * 12 * u, 34 * u, 7 * u, i % 2 ? 0xffe066 : 0xffffff)
        .setRotation(a)
        .setDepth(DEPTH);
      scene.tweens.add({
        targets: streak,
        x: p.x + Math.cos(a) * 92 * u,
        y: p.y + Math.sin(a) * 58 * u,
        scaleX: 0.15,
        alpha: 0,
        duration: 260,
        ease: "Quad.easeOut",
        onComplete: () => streak.destroy(),
      });
    }
  },
  /** Afterimage: a fading copy of the sprite as it is right now (shows up when the pose changes or moves). */
  ghost(scene, at) {
    const s = at.sprite;
    if (!s) return;
    const g = scene.add.image(s.x, s.y, s.texture.key, s.frame.name)
      .setOrigin(s.originX, s.originY)
      .setFlipX(s.flipX)
      .setScale(s.scaleX, s.scaleY)
      .setAngle(s.angle)
      .setAlpha(0.5)
      .setDepth(s.depth - 1);
    scene.tweens.add({ targets: g, alpha: 0, duration: 200, onComplete: () => g.destroy() });
  },
  /** Timing only: the ActionClock freezes the action; nothing to draw. */
  hitstop() {},
};

export function playFx(scene: Phaser.Scene, name: FxName, at: FxAt): void {
  FX[name](scene, at);
}
