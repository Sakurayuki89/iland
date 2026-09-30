import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

const ACTIONS_DIR = fileURLToPath(new URL("../../data/actions/", import.meta.url));

/**
 * Dev-server only: lets /lab.html read and save data/actions/<id>.json.
 * Same-origin JSON POSTs only, and the file name comes from a validated id.
 */
function labActions(): Plugin {
  return {
    name: "island-lab-actions",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__lab/actions", (req: IncomingMessage, res: ServerResponse) => {
        const send = (code: number, body: unknown): void => {
          res.statusCode = code;
          res.setHeader("content-type", "application/json");
          res.end(JSON.stringify(body));
        };
        if (req.method === "GET") {
          mkdirSync(ACTIONS_DIR, { recursive: true });
          const files = readdirSync(ACTIONS_DIR).filter((f) => f.endsWith(".json")).sort();
          return send(200, files.map((f) => JSON.parse(readFileSync(ACTIONS_DIR + f, "utf8"))));
        }
        if (req.method !== "POST") return send(405, { error: "GET or POST only" });
        const origin = req.headers.origin;
        if (origin && new URL(origin).host !== req.headers.host) return send(403, { error: "cross-origin" });
        if (!String(req.headers["content-type"] ?? "").startsWith("application/json")) return send(415, { error: "json only" });
        let body = "";
        req.on("data", (chunk: Buffer) => {
          body += chunk;
          if (body.length > 200_000) req.destroy();
        });
        req.on("end", () => {
          try {
            const action = JSON.parse(body) as { id?: unknown };
            if (typeof action.id !== "string" || !/^[a-z0-9_]{1,40}$/.test(action.id)) return send(400, { error: "bad id" });
            mkdirSync(ACTIONS_DIR, { recursive: true });
            writeFileSync(`${ACTIONS_DIR}${action.id}.json`, `${JSON.stringify(action, null, 2)}\n`);
            send(200, { saved: `data/actions/${action.id}.json` });
          } catch {
            send(400, { error: "invalid json" });
          }
        });
      });
    },
  };
}

// Game assets live in <repo>/assets and are served as-is (e.g. /sprites/cat_base.png).
export default defineConfig({
  plugins: [labActions()],
  publicDir: fileURLToPath(new URL("../../assets", import.meta.url)),
  server: { port: 5173, host: "127.0.0.1" },
  build: { chunkSizeWarningLimit: 2000 },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
