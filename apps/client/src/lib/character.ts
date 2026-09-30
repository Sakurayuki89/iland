import * as Phaser from "phaser";
import type { Direction } from "./direction";

/** Shape of <key>.anims.json written by tools/sprite_slicer.py. */
export interface AnimDef {
  key: string;
  frameRate: number;
  repeat: number;
  flipX: boolean;
  frames: { key: string; frame: string }[];
}
export interface AnimsFile {
  anims: AnimDef[];
}

export type Action = "idle" | "walk" | "net";

/** Anim keys are namespaced by texture so several characters can share "walk_down" etc. */
export const animKey = (textureKey: string, action: Action, dir: Direction): string =>
  `${textureKey}/${action}_${dir}`;

export function preloadCharacter(scene: Phaser.Scene, key: string): void {
  scene.load.atlas(key, `sprites/${key}.png`, `sprites/${key}.json`);
  scene.load.json(`${key}:anims`, `sprites/${key}.anims.json`);
}

/** Registers the character's animations and returns which anim keys must be drawn flipped (right = mirrored left). */
export function createCharacterAnims(scene: Phaser.Scene, key: string): Map<string, boolean> {
  const file = scene.cache.json.get(`${key}:anims`) as AnimsFile;
  const flips = new Map<string, boolean>();
  for (const def of file.anims) {
    const k = `${key}/${def.key}`;
    flips.set(k, def.flipX);
    if (scene.anims.exists(k)) continue;
    scene.anims.create({
      key: k,
      frameRate: def.frameRate,
      repeat: def.repeat,
      frames: def.frames.map((f) => ({ key, frame: f.frame })),
    });
  }
  return flips;
}
