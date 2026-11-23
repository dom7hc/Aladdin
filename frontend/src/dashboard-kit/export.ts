// One self-contained HTML file for a presentation: static slide markup, the
// dashboard's own theme CSS, slide layout CSS and a few lines of navigation.
// No React, modules, fonts or requests — the CSP forbids any network access,
// so the file behaves the same opened from a laptop with no connection.

const ALLOWED_ATTRIBUTES = new Set(["data-theme", "data-mode", "data-look"]);

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

/** Theme CSS is platform-owned, but it travels through JSON: never let it close the element. */
export function safeStyle(css: string): string {
  // CSS has no legitimate raw "<"; its escape keeps strings intact and nothing can close the element.
  return css.replace(/</g, "\\3c ");
}

export function rootAttributes(attributes: Record<string, string>): string {
  return Object.entries(attributes)
    .filter(([name]) => ALLOWED_ATTRIBUTES.has(name))
    .map(([name, value]) => ` ${name}="${escapeHtml(String(value))}"`)
    .join("");
}

export const SLIDE_CSS = `
html, body { margin: 0; background: #0b0d12; }
body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; -webkit-font-smoothing: antialiased; }
.deck { position: relative; }
.slide { box-sizing: border-box; width: 1600px; height: 900px; padding: 88px 112px 72px;
  background: var(--surface-0, #fff); color: var(--ink-1, #111); position: relative; overflow: hidden;
  display: flex; flex-direction: column; font-variant-numeric: tabular-nums; }
.slide::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 6px; background: var(--accent, #2563eb); }
.slide-body { flex: 1; display: flex; flex-direction: column; justify-content: center; min-height: 0; }
.slide h1 { font-size: 88px; line-height: 1.05; margin: 24px 0 0; letter-spacing: -0.02em; max-width: 1250px; }
.slide h2 { font-size: 44px; line-height: 1.15; margin: 0 0 28px; letter-spacing: -0.01em; max-width: 1300px; }
.slide-statement { font-size: 56px !important; font-weight: 600; max-width: 1250px; }
.slide-kicker { text-transform: uppercase; letter-spacing: .12em; font-size: 20px; font-weight: 700;
  color: var(--accent, #2563eb); margin: 0 0 24px; }
.slide-lede { font-size: 30px; color: var(--ink-2, #444); margin: 32px 0 0; }
.slide-scope { font-size: 20px; margin: 16px 0 0; opacity: .8; }
.slide-pill { align-self: flex-start; font-size: 18px; font-weight: 700; padding: 8px 18px; border-radius: 999px;
  background: var(--accent-soft, #e8efff); color: var(--accent, #2563eb); }
.slide.slide-title { background: linear-gradient(135deg, var(--accent, #2563eb), color-mix(in srgb, var(--accent, #2563eb) 55%, #050814)); color: #fff; }
.slide.slide-title::before { display: none; }
.slide.slide-title h1 { font-size: 104px; }
.slide.slide-title .slide-lede, .slide.slide-title .slide-footer { color: rgba(255,255,255,.82); border-color: rgba(255,255,255,.25); }
.slide.slide-title .slide-pill { background: #fff; color: var(--accent, #2563eb); }
.slide-hero { margin: 0; display: flex; align-items: baseline; gap: 18px; }
.slide-hero-value { font-size: 200px; font-weight: 800; line-height: 1; letter-spacing: -0.04em; }
.slide-hero-unit { font-size: 48px; color: var(--ink-2, #444); }
.slide-delta { display: inline-block; align-self: flex-start; margin: 28px 0 0; font-size: 30px; font-weight: 700;
  padding: 10px 22px; border-radius: 12px; }
.slide-delta-vs { font-weight: 500; opacity: .8; }
.tone-good { background: color-mix(in srgb, var(--good, #15803d) 14%, transparent); color: var(--good, #15803d); }
.tone-bad { background: color-mix(in srgb, var(--critical, #b91c1c) 14%, transparent); color: var(--critical, #b91c1c); }
.tone-neutral { background: var(--surface-2, #eee); color: var(--ink-2, #444); }
.slide-insight { font-size: 34px; line-height: 1.35; margin: 40px 0 0; max-width: 980px; }
.slide-body.slide-headline { flex-direction: row; align-items: center; gap: 64px; }
.slide-headline-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.slide-supporting { display: flex; flex-direction: column; gap: 24px; width: 320px; }
.slide-tile { border: 1px solid var(--line, #e2e2e2); border-radius: 20px; padding: 24px 28px; background: var(--surface-1, #fafafa); }
.slide-tile-label { margin: 0; font-size: 18px; color: var(--ink-3, #777); }
.slide-tile-value { margin: 10px 0 0; font-size: 52px; font-weight: 700; letter-spacing: -0.02em; }
.slide-tile-value span { font-size: 22px; font-weight: 500; color: var(--ink-2, #444); }
.slide-chart .slide-body { justify-content: flex-start; }
/* Charts are drawn at 900px (see renderPresentation) and zoomed, so labels grow with them. */
.slide-plot { width: 900px; zoom: 1.52; flex: 1; min-height: 0; display: flex; align-items: center; }
.slide-plot > * { width: 100%; }
.slide-plot svg { overflow: visible; }
.slide-list { font-size: 40px; line-height: 1.4; padding-left: 1.2em; margin: 0; max-width: 1300px; }
.slide-list li + li { margin-top: 20px; }
.slide-list li::marker { color: var(--accent, #2563eb); font-weight: 700; }
.slide-footer { display: flex; justify-content: space-between; gap: 24px; font-size: 18px; color: var(--ink-3, #777);
  border-top: 1px solid var(--line-soft, #e5e5e5); padding-top: 18px; }
.slide-number { font-weight: 600; }
@media screen {
  body { height: 100vh; overflow: hidden; display: grid; place-items: center; }
  .deck { width: 1600px; height: 900px; transform-origin: center; transform: scale(var(--fit, 1)); }
  .slide { position: absolute; inset: 0; display: none; }
  .slide.is-current { display: flex; }
}
@media print {
  @page { size: 1600px 900px; margin: 0; }
  .slide { break-after: page; display: flex; }
}
@media (prefers-reduced-motion: no-preference) {
  .slide.is-current .slide-body { animation: slide-in 220ms ease-out; }
}
@keyframes slide-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
`;

/** Arrow/space/click navigation, F for full screen, #n deep links, fit to window. */
export const NAV_SCRIPT = `(() => {
  const slides = [...document.querySelectorAll(".slide")];
  const deck = document.querySelector(".deck");
  let i = Math.min(Math.max((parseInt(location.hash.slice(1), 10) || 1) - 1, 0), slides.length - 1);
  const show = n => {
    i = Math.min(Math.max(n, 0), slides.length - 1);
    slides.forEach((s, k) => s.classList.toggle("is-current", k === i));
    history.replaceState(null, "", "#" + (i + 1));
  };
  const fit = () => deck.style.setProperty("--fit", Math.min(innerWidth / 1600, innerHeight / 900));
  addEventListener("resize", fit);
  addEventListener("keydown", e => {
    if (["ArrowRight", "PageDown", " ", "Enter"].includes(e.key)) { e.preventDefault(); show(i + 1); }
    else if (["ArrowLeft", "PageUp", "Backspace"].includes(e.key)) { e.preventDefault(); show(i - 1); }
    else if (e.key === "Home") show(0);
    else if (e.key === "End") show(slides.length - 1);
    else if (e.key === "f" || e.key === "F") {
      if (document.fullscreenElement) document.exitFullscreen?.();
      else document.documentElement.requestFullscreen?.().catch(() => {});
    }
  });
  addEventListener("click", e => show(e.clientX < innerWidth / 3 ? i - 1 : i + 1));
  fit(); show(i);
})();`;

export const CSP = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:";

export function buildStandaloneHtml({ title, bodyHtml, themeCss, attributes }: {
  title: string; bodyHtml: string; themeCss: string; attributes: Record<string, string>;
}): string {
  return `<!doctype html>
<html lang="en"${rootAttributes(attributes)}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="${CSP}">
<title>${escapeHtml(title)}</title>
<style>${safeStyle(themeCss)}</style>
<style>${SLIDE_CSS}</style>
</head>
<body>
${bodyHtml}
<script>${NAV_SCRIPT}</script>
</body>
</html>
`;
}
