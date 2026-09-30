import { describe, expect, it } from "vitest";
import { directionFromVector } from "./direction";

describe("directionFromVector", () => {
  it("picks the dominant axis", () => {
    expect(directionFromVector(10, 2)).toBe("right");
    expect(directionFromVector(-10, 2)).toBe("left");
    expect(directionFromVector(2, 10)).toBe("down");
    expect(directionFromVector(2, -10)).toBe("up");
  });

  it("keeps the previous facing when standing still", () => {
    expect(directionFromVector(0, 0, "left")).toBe("left");
    expect(directionFromVector(0, 0)).toBe("down");
  });

  it("prefers vertical on a perfect diagonal", () => {
    expect(directionFromVector(5, 5)).toBe("down");
    expect(directionFromVector(-5, -5)).toBe("up");
  });
});
