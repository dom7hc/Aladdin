import test from "node:test";
import assert from "node:assert/strict";
import { openInNewTab, POPUP_BLOCKED } from "./openInNewTab.ts";

test("a blocked pop-up is an error and never navigates the result page", async () => {
  let rendered = false;
  await assert.rejects(openInNewTab(() => null, async () => { rendered = true; return "x"; }, h => h), new RegExp(POPUP_BLOCKED.slice(0, 30)));
  assert.equal(rendered, false);
});

test("a tab closed before the slides are ready is left alone", async () => {
  const tab = { opener: {}, closed: false, location: { href: "about:blank" }, close() { this.closed = true; } };
  await openInNewTab(() => tab, async () => { tab.closed = true; return "<html>"; }, () => "blob:x");
  assert.equal(tab.location.href, "about:blank");
  assert.equal(tab.opener, null);
});

test("the slides load into the new tab; a render failure closes it", async () => {
  const tab = { opener: {}, closed: false, location: { href: "about:blank" }, close() { this.closed = true; } };
  await openInNewTab(() => tab, async () => "<html>", () => "blob:deck");
  assert.equal(tab.location.href, "blob:deck");
  const bad = { opener: {}, closed: false, location: { href: "about:blank" }, close() { this.closed = true; } };
  await assert.rejects(openInNewTab(() => bad, async () => { throw new Error("boom"); }, h => h), /boom/);
  assert.equal(bad.closed, true);
});
