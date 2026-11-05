# Vendored design data

`colors.csv`, `typography.csv`, `products.csv` and `ui-reasoning.csv` come from
**ui-ux-pro-max-skill**:

- Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- Path upstream: `src/ui-ux-pro-max/data/`
- Licence: MIT — see `LICENSE` in this directory
- Vendored: 2026-09-30 (colours, typography); 2026-11-05 (products, reasoning)

## Why vendored rather than installed

That project is a **Claude Code skill**: it expects an agent with a Skill tool.
Our generator is DeepSeek behind an OpenAI-compatible API and has no such
mechanism, so the skill cannot be "installed" for it. The data, however, is
plain CSV and directly usable — 192 palettes keyed by product type and 74 font
pairings with an industry column to match on.

## What we use, and what we deliberately do not

Used: palette colour roles (primary, background, foreground, card, muted,
border, destructive) and the heading/body font pairing. These drive a generated
dashboard's chrome.

**Not used for chart series colours.** These are brand palettes with no
guarantee of categorical separation or colourblind distinctness. Chart series
keep the validated eight-hue set in the template's `kit/theme.css`. Mixing the
two would quietly lose that property.

Palettes are also contrast-checked on load (`app/design/systems.py`) and
excluded if a pair a reader must read falls below WCAG AA, so an unreadable
palette can never be handed to a project.

## Looks (styles)

The ten looks in the template's `kit/looks.css` are implemented from
ui-ux-pro-max's `styles.csv` (same repository and licence): its style ids are
used verbatim, and each look follows that row's radius, shadow, spacing and
effect guidance. The CSV itself is not vendored: only the ten ids and a
condensed "best for" line live in `app/design/systems.py` (`STYLES`).
Chosen for dashboards: active upstream, light and dark supported, and
accessibility risk low or manageable. HUD and dimensional-layering styles were
left out for their high accessibility risk, and landing-page styles because
they are deprecated upstream.

## Reasoning (products, ui-reasoning)

`products.csv` and `ui-reasoning.csv` are the skill's reasoning engine: one row
per product category (192, aligned with `colors.csv`) giving its dashboard
style, style priority, colour and type mood, key effects and anti-patterns.
`app/design/reasoning.py` runs the same lookup the skill's `design_system.py`
does, on the server, and hands the architect a short brief in ids it can pick.

Two deliberate departures from upstream:

- **Matching.** Upstream ranks categories with BM25 over the whole catalogue,
  which is mostly consumer apps and landing pages; on business briefs that
  put attrition on "Sports Team/Club" and CSAT on "Autonomous Drone Fleet
  Manager". We match against a short table of business domains (HR, sales,
  finance, operations, ...) instead, each pointing at the upstream category
  whose rule fits it, with "Analytics Dashboard" as the fallback.
- **Decision rules** (`Decision_Rules`) are not applied. Across all 192 rows
  only ten touch a style, and those mostly name styles we do not implement.

`styles.csv`, `charts.csv` and the scripts are still not vendored: the ten
looks are hand-implemented (see Looks above), and the chart guidance the architect needs
is condensed into its prompt (donut for share of a whole, at most six slices;
progress for performance against a target; never series told apart by hue
alone).
