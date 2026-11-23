# HTML presentation

Every finished project gets a 16:9 HTML presentation instead of the old `.pptx`.

## How it works

1. **Capture (backend, at generation).** After the tester step, `app/generation/snapshot.py`
   runs the generated app once in an isolated child process and stores the real payloads
   of its dashboard endpoints. `app/presentation/service.py` publishes
   `generated/<id>/presentation/{input.json,manifest.json}` (spec, snapshot, theme CSS,
   requirement copy, hashes). If capture fails the project is still READY and the
   presentation is marked unavailable with a reason; nothing is invented.
2. **Serve.** `GET /api/projects/{id}/presentation-input` returns the stored input only
   (200, or 404 unknown / 409 not available with a reason). It never runs generated code.
3. **Render (browser).** The result page's **Open presentation** / **Download presentation**
   fetch the input, render the slides off-screen with the shared dashboard kit
   (`frontend/src/dashboard-kit/presentation.tsx`), and freeze them into one
   self-contained HTML file (`dashboard-kit/export.ts`). Both buttons use the same bytes.

## Guarantees

- **Same numbers as the dashboard**: slides use the dashboard's own `heroFact`/`chartFacts`
  on the captured payloads (tested in `presentation.test.mjs`).
- **Offline**: no scripts, fonts or images are loaded; a CSP forbids any request.
- **Safe text**: requirement and payload strings are escaped; theme CSS cannot close its tag.
- **Honest**: sample data is labelled on the title slide and every footer; missing
  requirements shorten the deck instead of padding it.

## Presenting

Arrow keys, space or click to move; **F** for full screen; `#3` in the URL opens slide 3;
printing gives one slide per page.

The legacy `GET /api/projects/{id}/deck` (.pptx) endpoint still exists for compatibility
but is no longer offered in the UI.
