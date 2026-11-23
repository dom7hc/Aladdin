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

test("mock serves a single project and, once READY, its sample presentation input", async () => {
  const { handleMockRequest, createProject: create } = await import("./handlers.ts");
  const { getState } = await import("./store.ts");
  const call = (method, path, body = {}) => handleMockRequest({ method, path, body, headers: {} });
  const p = create("Budget review for cost centres", "budget-vs-actual");
  assert.equal(call("GET", `/projects/${p.id}`).id, p.id);
  call("POST", `/projects/${p.id}/chat`, { message: "Owners learn about overspend weeks after month end." });
  call("POST", `/projects/${p.id}/requirements/autofill`);
  call("POST", `/projects/${p.id}/requirements/finalize`);
  call("POST", `/projects/${p.id}/generate`);
  assert.throws(() => call("GET", `/projects/${p.id}/presentation-input`), /READY/);
  getState().generation[p.id].startedAt = Date.now() - 60_000;
  assert.equal(call("GET", `/projects/${p.id}/status`).presentation.status, "available");
  const input = call("GET", `/projects/${p.id}/presentation-input`);
  assert.equal(input.snapshot.provenance.kind, "sample");
});

test("mock never shows one starter another starter's slides", async () => {
  const { handleMockRequest, createProject: create } = await import("./handlers.ts");
  const { getState } = await import("./store.ts");
  const call = (method, path, body = {}) => handleMockRequest({ method, path, body, headers: {} });
  const p = create("How healthy is our hiring pipeline", "hiring-pipeline");
  call("POST", `/projects/${p.id}/chat`, { message: "Roles stay open for months and nobody knows the bottleneck." });
  call("POST", `/projects/${p.id}/requirements/autofill`);
  call("POST", `/projects/${p.id}/requirements/finalize`);
  call("POST", `/projects/${p.id}/generate`);
  getState().generation[p.id].startedAt = Date.now() - 60_000;
  const status = call("GET", `/projects/${p.id}/status`);
  assert.equal(status.presentation.status, "unavailable");
  assert.match(status.presentation.reason, /only for the Budget versus actual/);
  assert.throws(() => call("GET", `/projects/${p.id}/presentation-input`), /only for the Budget/);
});
