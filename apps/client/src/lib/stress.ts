import * as Phaser from "phaser";
import { type Action, animKey } from "./character";
import { type Direction, directionFromVector } from "./direction";

interface Wanderer {
  sprite: Phaser.GameObjects.Sprite;
  key: string;
  flips: Map<string, boolean>;
  tx: number;
  ty: number;
  speed: number;
  dir: Direction;
}

/**
 * Perf harness: N sprites wandering at random, drawn like real characters (per-frame move,
 * feet-based depth, anim + flip switching). No game rules — used by ?stress=N and tools/bench.py.
 */
export function spawnWanderers(
  scene: Phaser.Scene,
  n: number,
  keys: readonly string[],
  flipsByKey: Map<string, Map<string, boolean>>,
  scale: number,
): (deltaMs: number) => void {
  const { width, height } = scene.scale;
  const list: Wanderer[] = [];
  const pick = () => ({
    x: Phaser.Math.Between(40, width - 40),
    y: Phaser.Math.Between(Math.round(height * 0.3), height - 20),
  });
  for (let i = 0; i < n; i++) {
    const key = keys[i % keys.length] as string;
    const p = pick();
    const sprite = scene.add.sprite(p.x, p.y, key, "down_idle").setScale(scale);
    const t = pick();
    list.push({ sprite, key, flips: flipsByKey.get(key) ?? new Map(), tx: t.x, ty: t.y, speed: Phaser.Math.Between(60, 140), dir: "down" });
  }

  const play = (w: Wanderer, action: Action, dir: Direction) => {
    const k = animKey(w.key, action, dir);
    w.sprite.setFlipX(w.flips.get(k) ?? false);
    w.sprite.anims.play(k, true);
  };
  list.forEach((w) => play(w, "walk", w.dir));

  return (deltaMs: number) => {
    const step = deltaMs / 1000;
    for (const w of list) {
      const dx = w.tx - w.sprite.x;
      const dy = w.ty - w.sprite.y;
      const dist = Math.hypot(dx, dy);
      if (dist < 4) {
        const t = pick();
        w.tx = t.x;
        w.ty = t.y;
        continue;
      }
      const d = directionFromVector(dx, dy, w.dir);
      if (d !== w.dir) {
        w.dir = d;
        play(w, "walk", d);
      }
      w.sprite.x += (dx / dist) * w.speed * step;
      w.sprite.y += (dy / dist) * w.speed * step;
      w.sprite.setDepth(w.sprite.y);
    }
  };
}
