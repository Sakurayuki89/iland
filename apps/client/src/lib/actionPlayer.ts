import * as Phaser from "phaser";
import type { Pose } from "./action";
import type { Direction } from "./direction";

export interface PoseBase {
  x: number;
  y: number;
  scale: number;
}

const FORWARD: Record<Direction, readonly [number, number]> = { left: [-1, 0], right: [1, 0], down: [0, 1], up: [0, -1] };

/**
 * Draws one sampled pose on a sprite whose origin is at the feet (the atlas pivot).
 * Right-facing reuses the left frames mirrored. Returns false when the atlas lacks the frame.
 */
export function applyPose(sprite: Phaser.GameObjects.Sprite, pose: Pose, dir: Direction, base: PoseBase): boolean {
  const frame = `${dir === "right" ? "left" : dir}_${pose.frame}`;
  const has = sprite.texture.has(frame);
  if (has && sprite.frame.name !== frame) sprite.setFrame(frame);
  sprite.setFlipX(dir === "right");

  const side = dir === "left" || dir === "right";
  const sign = dir === "left" ? -1 : 1;
  const [fx, fy] = FORWARD[dir];
  sprite.setPosition(base.x + fx * pose.x * base.scale, base.y + fy * pose.x * base.scale - pose.lift * base.scale);
  sprite.setScale(base.scale * pose.scaleX, base.scale * pose.scaleY);
  sprite.setAngle(pose.rotation * sign + (side ? pose.lean * sign : 0));
  sprite.setAlpha(pose.alpha);
  return has;
}
