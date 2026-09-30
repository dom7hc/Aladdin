"""Per-project design systems, chosen from vendored ui-ux-pro-max data.

See data/PROVENANCE.md for where the CSVs come from and under what licence.

A design system here is a **palette plus a font pairing**, selected to suit the
user's industry. It drives the dashboard's chrome — accent, surfaces, ink,
borders. It deliberately does NOT touch chart series colours: these are brand
palettes, not categorical palettes, and have no guarantee of colourblind
separation. Charts keep the validated eight-hue set in kit/theme.css.

Every palette is contrast-checked at import and excluded if it fails, so a
project can never be given an unreadable one.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# WCAG AA for normal text. Applied to the pairs a reader actually has to read.
MIN_CONTRAST = 4.5

# WCAG AA for non-text UI components. The accent is mostly buttons, borders and
# active states rather than body text, so 3:1 is the right bar for it.
#
# Checking this is not theoretical: the vendored "Financial Dashboard" palette
# pairs primary #0F172A with background #020617 — a ratio of 1.13, an accent
# nobody could see. Requiring 4.5 here instead would drop 92 of 173 palettes for
# no accessibility gain, so the accent must not be used for small text on a
# surface anywhere in the kit.
MIN_UI_CONTRAST = 3.0

# One variable file per family, not one per weight.
#
# Measured: pinning 400;600;700 for Poppins + Open Sans costs 926 kB across all
# unicode-range subsets, while the variable range costs 256 kB — three static
# files lose to one variable file per subset. The same inversion showed up on the
# platform's own body font earlier, where "optimising" to four weights made it
# four times bigger.
#
# Caveat worth knowing: those totals cover every subset Google emits, and a
# browser fetches only the ones it needs, so the real per-visitor cost is a
# fraction of both numbers. The comparison still holds — variable wins either
# way — but treat the absolute figures as an upper bound, not a measurement.
FONT_WEIGHT_RANGE = "400..700"


def _luminance(hex_colour: str) -> float:
    value = hex_colour.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    channels = []
    for offset in (0, 2, 4):
        channel = int(value[offset : offset + 2], 16) / 255
        channels.append(
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        )
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: str, second: str) -> float:
    """WCAG contrast ratio. Symmetric, so argument order does not matter."""
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# The kit's dark surfaces, from templates/.../kit/theme.css. The vendored
# palettes are light-mode only, so a dark-mode accent has to be derived.
DARK_SURFACE = "#141821"
DARK_CARD = "#1b202b"


def _channels(hex_colour: str) -> tuple[int, int, int]:
    value = hex_colour.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _mix_with_white(hex_colour: str, amount: float) -> str:
    red, green, blue = _channels(hex_colour)
    mixed = tuple(round(c + (255 - c) * amount) for c in (red, green, blue))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def accent_for_dark(primary: str) -> str:
    """A usable dark-mode accent derived from a light-mode primary.

    The vendored palettes supply one primary, chosen against a light
    background. Reusing it on the kit's dark surface leaves it near-invisible —
    #0369A1 on #141821 is about 2.2:1 — so lighten it until it clears the UI
    threshold against both dark surfaces. Returns the original when it already
    passes, so palettes that happen to be light-friendly are left alone.
    """
    for step in range(11):
        candidate = _mix_with_white(primary, step / 10)
        if all(
            contrast(candidate, surface) >= MIN_UI_CONTRAST for surface in (DARK_SURFACE, DARK_CARD)
        ):
            return candidate
    return "#ffffff"


@dataclass(frozen=True)
class Palette:
    id: str
    product_type: str
    primary: str
    on_primary: str
    accent: str
    background: str
    foreground: str
    card: str
    card_foreground: str
    muted: str
    muted_foreground: str
    border: str
    destructive: str

    def readable(self) -> bool:
        """True when the pairs a reader must read all clear WCAG AA.

        Checked rather than trusted: these are brand palettes from a third-party
        dataset, and an unreadable dashboard is worse than a plain one.
        """
        text_ok = all(
            contrast(fg, bg) >= MIN_CONTRAST
            for fg, bg in (
                (self.foreground, self.background),
                (self.card_foreground, self.card),
                (self.on_primary, self.primary),
                (self.muted_foreground, self.muted),
            )
        )
        # The accent must be visible on both surfaces it sits on, or buttons and
        # active states disappear.
        accent_ok = all(
            contrast(self.primary, surface) >= MIN_UI_CONTRAST
            for surface in (self.background, self.card)
        )
        return text_ok and accent_ok


@dataclass(frozen=True)
class FontPairing:
    id: str
    name: str
    heading: str
    body: str
    keywords: str
    best_for: str

    def google_url(self) -> str:
        """One variable file per family, over the weight range the kit uses."""
        families = [
            f"family={family.replace(' ', '+')}:wght@{FONT_WEIGHT_RANGE}"
            for family in dict.fromkeys((self.heading, self.body))  # dedupe, keep order
        ]
        return "https://fonts.googleapis.com/css2?" + "&".join(families) + "&display=swap"


@dataclass(frozen=True)
class DesignSystem:
    palette: Palette
    fonts: FontPairing


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def _rows(name: str) -> list[dict[str, str]]:
    # utf-8-sig: the upstream CSVs carry a byte-order mark.
    with (DATA_DIR / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


@lru_cache(maxsize=1)
def palettes() -> tuple[Palette, ...]:
    """Every vendored palette that is legible. Unreadable ones are dropped."""
    loaded = []
    for row in _rows("colors.csv"):
        product = (row.get("Product Type") or "").strip()
        if not product:
            continue
        values = {
            "primary": row["Primary"],
            "on_primary": row["On Primary"],
            "accent": row["Accent"],
            "background": row["Background"],
            "foreground": row["Foreground"],
            "card": row["Card"],
            "card_foreground": row["Card Foreground"],
            "muted": row["Muted"],
            "muted_foreground": row["Muted Foreground"],
            "border": row["Border"],
            "destructive": row["Destructive"],
        }
        if not all(_HEX.match((v or "").strip()) for v in values.values()):
            continue
        palette = Palette(
            id=_slug(product),
            product_type=product,
            **{k: v.strip() for k, v in values.items()},
        )
        if palette.readable():
            loaded.append(palette)
    return tuple(loaded)


@lru_cache(maxsize=1)
def pairings() -> tuple[FontPairing, ...]:
    loaded = []
    for row in _rows("typography.csv"):
        name = (row.get("Font Pairing Name") or "").strip()
        heading = (row.get("Heading Font") or "").strip()
        body = (row.get("Body Font") or "").strip()
        if not (name and heading and body):
            continue
        loaded.append(
            FontPairing(
                id=_slug(name),
                name=name,
                heading=heading,
                body=body,
                keywords=(row.get("Mood/Style Keywords") or "").strip(),
                best_for=(row.get("Best For") or "").strip(),
            )
        )
    return tuple(loaded)


def excluded_palette_count() -> int:
    """How many vendored palettes were dropped as unreadable."""
    return len([r for r in _rows("colors.csv") if (r.get("Product Type") or "").strip()]) - len(
        palettes()
    )


DEFAULT_PALETTE_ID = "saas-general"
DEFAULT_PAIRING_ID = "modern-professional"


def palette_by_id(palette_id: str | None) -> Palette:
    lookup = {p.id: p for p in palettes()}
    return lookup.get(palette_id or "") or lookup.get(DEFAULT_PALETTE_ID) or palettes()[0]


def pairing_by_id(pairing_id: str | None) -> FontPairing:
    lookup = {p.id: p for p in pairings()}
    return lookup.get(pairing_id or "") or lookup.get(DEFAULT_PAIRING_ID) or pairings()[0]


def resolve(palette_id: str | None, pairing_id: str | None) -> DesignSystem:
    """Always returns something usable, whatever the model asked for."""
    return DesignSystem(palette=palette_by_id(palette_id), fonts=pairing_by_id(pairing_id))


def choices_for_prompt(limit: int = 60) -> str:
    """Palette ids and their industries, for the architect's system prompt.

    Capped because the full 192 would crowd out the rest of the instruction.
    """
    return "\n".join(f"- {p.id}: {p.product_type}" for p in palettes()[:limit])


def pairing_choices_for_prompt(limit: int = 24) -> str:
    return "\n".join(f"- {p.id}: {p.name} — {p.best_for[:70]}" for p in pairings()[:limit])


def design_css(system: DesignSystem) -> str:
    """The per-project token overrides the kit consumes.

    Chart series colours are deliberately absent: theme.css owns those, and they
    are validated for categorical separation in a way brand palettes are not.
    """
    palette = system.palette
    fonts = system.fonts
    # Derived, not reused: see accent_for_dark.
    dark_accent = accent_for_dark(palette.primary)
    dark_accent_soft = _mix_with_white(DARK_SURFACE, 0.06)
    return f"""/* Generated for this project. Do not edit by hand.
 *
 * Palette:  {palette.product_type} ({palette.id})
 * Fonts:    {fonts.name} — {fonts.heading} over {fonts.body}
 *
 * Source: ui-ux-pro-max (MIT) — see the platform's design/data/PROVENANCE.md.
 * Chart series colours are NOT set here; theme.css owns those because they are
 * validated for colourblind separation and these brand palettes are not.
 *
 * Only light-mode surfaces are overridden. theme.css keeps its dark neutrals,
 * which are already checked against the series palette; the dark accent below
 * is derived from the light primary so it stays visible on them.
 */
@import url("{fonts.google_url()}");

:root {{
  --surface-0: {palette.card};
  --surface-1: {palette.background};
  --surface-2: {palette.muted};
  --ink-1: {palette.foreground};
  --ink-2: {palette.muted_foreground};
  --ink-3: {palette.muted_foreground};
  --line: {palette.border};
  --line-soft: {palette.muted};

  --accent-l: {palette.primary};
  --accent-d: {dark_accent};
  --accent-soft-l: {palette.muted};
  --accent-soft-d: {dark_accent_soft};
  --accent-ink: {palette.on_primary};

  --critical: {palette.destructive};

  --font-body: "{fonts.body}", ui-sans-serif, system-ui, sans-serif;
  --font-heading: "{fonts.heading}", var(--font-body);
}}

body {{
  font-family: var(--font-body);
}}

h1,
h2,
h3,
.shell-title,
.card-title,
.tile-value {{
  font-family: var(--font-heading);
}}
"""
