# Design systems, file upload, CRUD — progress and what's left

Status as of 2026-09-30. Branch: `feature/design-systems` (commit `06f1132`),
based on `main` at `c78a38b`.

Three asks were planned together:

| # | Ask | State |
| --- | --- | --- |
| A | Use the ui-ux-pro-max skill for per-project UI/UX | **Done**, on this branch, not yet merged |
| B | Generated dashboard persists real records | **Done by a teammate** in `c78a38b`, via SQLite |
| C | Upload a spreadsheet and build the dashboard on it | **Not started** |
| D | Create / edit / delete records in the output | **Done by a teammate** in `c78a38b` |

B and D were implemented independently while A was in progress, so the plan's
original sequencing no longer applies. What remains is C, plus the follow-ups
listed at the end.

---

## A. Per-project design systems — done

### The key constraint

`nextlevelbuilder/ui-ux-pro-max-skill` is a **Claude Code skill**: it expects an
agent with a Skill tool. Our generator is DeepSeek behind an OpenAI-compatible
API and has none, so the skill cannot be installed for it.

Its *data* is plain CSV and directly usable. That is what we vendored:
`app/design/data/colors.csv` (192 palettes keyed by product type) and
`typography.csv` (74 font pairings with an industry column), plus the upstream
MIT `LICENSE` and a `PROVENANCE.md`.

### How it works

1. The architect picks `designSystem: {palette, fonts}` by matching the user's
   industry. The prompt offers a capped list (60 palettes, 24 pairings) —
   the full 192 would crowd out the rest of the instruction.
2. `app/design/systems.py` resolves the ids. **Unknown ids fall back to the
   default** rather than failing a generation over cosmetics.
3. The **platform**, not the model, writes `frontend/src/kit/design.css`.
   `App.tsx` imports it after `theme.css` so its tokens win. The template ships
   a default copy so the import always resolves.

### Two things the vendored data is not trusted with

**Chart series colours stay in `theme.css`.** These are brand palettes with no
guarantee of categorical separation or colourblind distinctness. A test asserts
`design.css` never sets a `--series-*` token. Do not relax this.

**Legibility is computed, not assumed. 44 of 192 palettes are excluded:**

- 19 fail WCAG AA (4.5:1) on text pairs.
- 25 more fail 3:1 on the accent against its own surfaces.

The clearest case is `Financial Dashboard`: primary `#0F172A` on background
`#020617`, a ratio of **1.13** — an accent nobody could see. It passed a
text-only check, which is why the accent check exists. 3:1 rather than 4.5:1 is
deliberate: it is the WCAG bar for non-text UI components, and 4.5 would drop 92
of 173 palettes for no accessibility gain. The consequence is that **the accent
must never be used for small text on a surface** anywhere in the kit.

**Dark mode is derived.** The vendored palettes are light-mode only, so reusing a
light primary on the kit's dark surface leaves it invisible.
`accent_for_dark()` lightens it until it clears 3:1 on both dark surfaces; every
surviving palette passes afterwards.

### Fonts: pinning weights is the trap, not the fix

Measured for Poppins + Open Sans:

| form | total font bytes |
| --- | --- |
| pinned `400;600;700` | 926,652 |
| variable range `400..700` | 256,060 |

Three static files per unicode subset lose to one variable file. The same
inversion appeared earlier on the platform's own body font, where "optimising"
to four weights made it four times bigger.

**Caveat, stated honestly:** those totals span every `unicode-range` subset
Google emits, and a browser fetches only the subsets it needs. The real
per-visitor cost is a fraction of both figures. The comparison holds either way,
but the absolute numbers are an upper bound, not a measurement. **If someone
wants a real number, measure only the blocks whose `unicode-range` covers basic
latin** — my attempt at that returned 0 files because the range string format
did not match my filter, and I stopped rather than keep burning time on it.

The plan's "fall back to the system stack above ~80 kB" rule is therefore
**not implemented** — the budget cannot be enforced against a number we have
not measured properly. Decide the real threshold after measuring latin-only.

### Also in this commit: the PoC mongo container is gone

Generation moved to SQLite in `c78a38b`, which left a 512 MB `poc-mongo` service
and its healthcheck wait in **every** preview build, doing nothing. Removed.
The database now sits on a small volume at `/data/poc.db`, so records survive a
container restart within the preview's lifetime, and the path is overridable via
`POC_DB` so a downloaded project still runs outside the preview stack.

### Verified

- 169 backend tests pass; `ruff check` and `ruff format --check` clean.
- Platform frontend type-checks.
- The template frontend **builds with the generated `design.css`**: 36 modules,
  CSS 8.00 kB (was 7.21), JS unchanged. The bundle keeps all eight series tokens
  and the pinned font URL survives bundling.

### Not verified — do this before trusting it

- **No generated dashboard has been rendered with a non-default palette yet.**
  The CSS is correct by construction and by test, but nobody has looked at one.
- Nothing is deployed. This branch is not merged and not on the VM.
- Light/dark has not been eyeballed on a real preview with a vendored palette.

---

## C. Spreadsheet upload — not started

Design as planned, unchanged by the teammate's work except that the seed target
is now **SQLite, not Mongo**:

1. `POST /api/projects/{id}/data` accepts one CSV or XLSX. CSV needs no
   dependency; Excel needs `openpyxl` adding to `backend/requirements.txt`.
2. `app/ingest/spreadsheet.py` parses to columns plus typed sample rows, infers
   column types, and caps rows, columns and cell size. **Uploads are the first
   untrusted input this product accepts** — size, row, column and type limits
   are part of the feature, not a later pass.
3. The parsed **schema** goes into the requirements so the architect designs
   widgets around columns that exist. The parsed **rows** become the seed the
   generated backend loads into SQLite on first start.
4. `ChatPage.tsx` gains an attach control and shows the detected columns back,
   so a wrong file is obvious before generating.

Rejection cases to test: a 50 MB file, 10,000 columns, and a `.exe` renamed to
`.csv`.

---

## Follow-ups, in the order I would do them

1. **Look at a generated dashboard with a vendored palette.** Cheapest way to
   find out whether this actually looks good rather than merely valid.
2. **Merge and deploy this branch**, then regenerate one project per layout.
   Existing projects keep the kit as copied at their generation time, so only
   new ones get design systems.
3. **Measure latin-only font cost** and then set a real budget with a fallback.
4. **Stage C**, the upload.

## Known issues not addressed here

- `develop` still drifts behind `main`.
- Deploys still do not wait for CI: the three workflows run in parallel on push
  to `main`, and `main` has no branch protection, so a red build reaches
  production.
- The icon font is still the platform's largest asset at 462 kB. Replacing
  Material Symbols with inline SVG for the ~20 icons actually used would take it
  to near zero.
