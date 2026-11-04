# Vendored design data

`colors.csv` and `typography.csv` come from **ui-ux-pro-max-skill**:

- Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- Path upstream: `src/ui-ux-pro-max/data/`
- Licence: MIT — see `LICENSE` in this directory
- Vendored: 2026-09-30

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
