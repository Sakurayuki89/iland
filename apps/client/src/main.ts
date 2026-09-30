import * as Phaser from "phaser";
import { SandboxScene } from "./scenes/SandboxScene";

new Phaser.Game({
  type: Phaser.AUTO,
  parent: "game",
  width: 960,
  height: 540,
  backgroundColor: "#b9d98a",
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: [SandboxScene],
});
