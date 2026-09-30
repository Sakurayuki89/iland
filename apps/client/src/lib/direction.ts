export type Direction = "down" | "up" | "left" | "right";

/** Facing for a movement vector (screen coords: +y is down). Keeps `previous` when not moving. */
export function directionFromVector(dx: number, dy: number, previous: Direction = "down"): Direction {
  if (dx === 0 && dy === 0) return previous;
  if (Math.abs(dx) > Math.abs(dy)) return dx < 0 ? "left" : "right";
  return dy < 0 ? "up" : "down";
}
