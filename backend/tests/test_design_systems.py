"""Per-project design systems from the vendored ui-ux-pro-max data.

The contrast gate is the point of this module: the palettes are a third-party
brand dataset, and 44 of the 192 are not legible enough to hand to a user.
"""

import re
from pathlib import Path

from app.design import systems as d


def test_palettes_and_pairings_load():
    assert len(d.palettes()) > 100, "the vendored data did not load"
    assert len(d.pairings()) > 50


def test_unreadable_palettes_are_excluded_not_shipped():
    """A palette a user cannot read is worse than a plain one."""
    assert d.excluded_palette_count() > 0, "the gate excluded nothing, so it is not working"
    for palette in d.palettes():
        assert palette.readable()


def test_the_invisible_accent_palette_is_gone():
    """Financial Dashboard pairs #0F172A on #020617 — a ratio of 1.13.

    It passed a text-only check because the accent was never compared with the
    background, and would have shipped an accent nobody could see.
    """
    assert round(d.contrast("#0F172A", "#020617"), 2) == 1.13
    assert "financial-dashboard" not in {p.id for p in d.palettes()}


def test_every_surviving_palette_has_a_visible_accent():
    for palette in d.palettes():
        for surface in (palette.background, palette.card):
            assert d.contrast(palette.primary, surface) >= d.MIN_UI_CONTRAST


def test_dark_accent_is_derived_and_always_visible():
    """The vendored palettes are light-mode only.

    Reusing a light primary on the kit's dark surface leaves it invisible, so a
    dark accent is lightened until it clears the UI threshold.
    """
    for palette in d.palettes():
        dark = d.accent_for_dark(palette.primary)
        for surface in (d.DARK_SURFACE, d.DARK_CARD):
            assert d.contrast(dark, surface) >= d.MIN_UI_CONTRAST, palette.id


def test_contrast_is_symmetric():
    assert d.contrast("#ffffff", "#000000") == d.contrast("#000000", "#ffffff")
    assert round(d.contrast("#ffffff", "#000000"), 1) == 21.0


def test_resolve_always_returns_something_usable():
    """An unknown id must fall back, never fail a generation over cosmetics."""
    for palette_id, fonts_id in ((None, None), ("nonsense", "nonsense"), ("", "")):
        system = d.resolve(palette_id, fonts_id)
        assert system.palette.readable()
        assert system.fonts.heading and system.fonts.body


def test_font_url_asks_for_one_variable_file_per_family():
    """Pinning weights is the trap, not the fix.

    Measured: 400;600;700 for this pairing costs 926 kB of font files against
    256 kB for the variable range, because three static files per subset lose to
    one variable file. Asserting the range keeps someone from "optimising" it
    back into separate weights.
    """
    url = d.pairing_by_id("modern-professional").google_url()
    assert f"wght@{d.FONT_WEIGHT_RANGE}" in url
    assert ";" not in url.split("wght@")[1].split("&")[0], "weights were pinned again"
    assert "display=swap" in url


def test_design_css_sets_chrome_but_never_chart_series():
    """Series colours are validated for colourblind separation; these are not."""
    css = d.design_css(d.resolve("job-board-recruitment", "modern-professional"))
    for token in ("--surface-0", "--ink-1", "--accent-l", "--accent-d", "--font-heading"):
        assert token in css
    for forbidden in ("--series-1", "--series-2", "--series-8"):
        assert forbidden not in css, "design.css must not touch the chart palette"


def test_design_css_scopes_the_accent_to_the_design_theme():
    """Under a fixed theme the user picked, this palette's accent and ink must not leak.

    theme.css sets accents under :root[data-theme=...], which outranks a bare
    :root; the swatch themes never set --accent-ink, so an unscoped ink would
    put this palette's text colour on their buttons.
    """
    css = d.design_css(d.resolve("medical-clinic", "corporate-trust"))
    root, scoped = css.split(':root[data-theme="design"]', 1)
    for token in ("--accent-l", "--accent-d", "--accent-ink"):
        assert token not in root
        assert token in scoped
    # The swatch's own token stays unscoped so it shows under any theme.
    assert "--design-accent" in root


def test_every_style_has_a_look_and_every_look_a_style():
    """The architect may only pick looks the kit can render, and vice versa."""
    looks_css = (
        Path(__file__).parents[1] / "templates/default-poc/frontend/src/kit/looks.css"
    ).read_text(encoding="utf-8")
    defined = set(re.findall(r':root\[data-look="([a-z0-9-]+)"\]', looks_css))
    assert defined == set(d.STYLES)
    assert d.DEFAULT_STYLE_ID in d.STYLES


def test_unknown_style_falls_back_to_the_default():
    assert d.resolve(None, None, "neon-vapor").style == d.DEFAULT_STYLE_ID
    assert d.resolve(None, None, "glassmorphism").style == "glassmorphism"


def test_template_ships_the_default_design_css():
    """The template's copy must match what the platform would write for it."""
    shipped = Path(__file__).parents[1] / "templates/default-poc/frontend/src/kit/design.css"
    assert shipped.read_text(encoding="utf-8") == d.design_css(d.resolve(None, None))


def test_design_css_dark_accent_differs_from_light_when_it_must():
    system = d.resolve("job-board-recruitment", "modern-professional")
    css = d.design_css(system)
    assert system.palette.primary.lower() in css.lower()
    # The derived dark accent is a distinct, lighter value.
    assert d.accent_for_dark(system.palette.primary).lower() in css.lower()
    assert d.accent_for_dark(system.palette.primary) != system.palette.primary


def test_prompt_choices_are_capped():
    """The full 192 would crowd the architect's instruction out of the prompt."""
    assert len(d.choices_for_prompt().splitlines()) <= 60
    assert len(d.pairing_choices_for_prompt().splitlines()) <= 24
