// Development/CI only; never run during generation or from backend runtime.
import { copyFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const core = new URL("../src/dashboard-kit/", import.meta.url);
const mirror = new URL("../../backend/templates/default-poc/frontend/src/kit/", import.meta.url);
await mkdir(fileURLToPath(mirror), { recursive: true });
for (const name of ["types.ts", "normalize.ts", "format.ts", "snapshot.ts", "insights.ts", "charts.tsx", "export.css"])
  await copyFile(new URL(name, core), new URL(name, mirror));
console.log("Shared dashboard kit mirror synchronized.");
