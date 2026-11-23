import test from "node:test";
import assert from "node:assert/strict";
import { createProject } from "./handlers.ts";
const values = new Map();
globalThis.localStorage = { getItem: k => values.get(k) ?? null, setItem: (k, v) => values.set(k, v) };

test("mock creation preserves explicit scenario and free text", () => {
  assert.equal(createProject("Hiring", "hiring-pipeline").scenarioId, "hiring-pipeline");
  assert.equal(createProject("Free text").scenarioId, null);
  assert.equal(createProject("Custom", "custom-role").scenarioId, "custom-role");
  for (const bad of ["", "../x", 123]) assert.throws(() => createProject("x", bad));
});
