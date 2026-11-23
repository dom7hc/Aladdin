// Browser adapter: render the slides off-screen at their real 1600×900 size,
// let the charts measure themselves, then freeze the committed DOM into one
// standalone HTML file. The browser serialiser escapes all text, so payload
// and requirement strings can never become markup.

import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";
import { buildStandaloneHtml } from "../dashboard-kit/export";
import { PresentationSlides, RENDERER_VERSION } from "../dashboard-kit/presentation";
import type { PresentationInput } from "../dashboard-kit/presentation";

const frame = () => new Promise<void>(resolve => requestAnimationFrame(() => resolve()));

/** Wait until the charts stop resizing (ResizeObserver settles in a frame or two). */
async function settle(host: HTMLElement, maxFrames = 30): Promise<void> {
  let last = "";
  let stable = 0;
  for (let n = 0; n < maxFrames && stable < 3; n++) {
    await frame();
    const now = [...host.querySelectorAll("svg")].map(svg => svg.getAttribute("width") ?? svg.getAttribute("viewBox")).join("|");
    stable = now === last ? stable + 1 : 0;
    last = now;
  }
}

export async function renderPresentationHtml(input: PresentationInput): Promise<string> {
  if (input.schemaVersion !== 1 || input.rendererVersion !== RENDERER_VERSION)
    throw new Error("This presentation was saved for a different version of Aladdin.");
  const host = document.createElement("div");
  host.setAttribute("aria-hidden", "true");
  // Off-screen but laid out at full size: display:none would give charts zero width.
  host.style.cssText = "position:fixed;left:-20000px;top:0;width:1600px;pointer-events:none;contain:layout style;";
  for (const [name, value] of Object.entries(input.theme.attributes)) host.setAttribute(name, value);
  const style = document.createElement("style");
  // Scope the deck's own layout while measuring; the export carries the full CSS.
  style.textContent = ".slide{box-sizing:border-box;width:1600px;height:900px;padding:88px 112px 72px;display:flex;flex-direction:column}.slide-body{flex:1;display:flex;flex-direction:column;min-height:0}.slide-plot{width:900px}.slide-plot>*{width:100%}";
  host.appendChild(style);
  const mount = document.createElement("div");
  host.appendChild(mount);
  document.body.appendChild(host);
  const root = createRoot(mount);
  try {
    flushSync(() => root.render(<PresentationSlides input={input} />));
    await settle(mount);
    const bodyHtml = mount.innerHTML;
    return buildStandaloneHtml({
      title: `${input.spec.title} — presentation`,
      bodyHtml,
      themeCss: input.theme.css,
      attributes: input.theme.attributes,
    });
  } finally {
    root.unmount();
    host.remove();
  }
}
