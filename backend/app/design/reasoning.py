"""Design reasoning from ui-ux-pro-max's rules, run on the server.

The skill itself cannot run here (see data/PROVENANCE.md), but its reasoning
engine is data plus a search: match the brief to one of 192 product categories,
then read that category's rule — style priority, colour and type mood, effects
and, most usefully, what to avoid. This module does the same with the vendored
``products.csv`` and ``ui-reasoning.csv`` and turns the result into a short
brief for the architect, in the ids it can actually pick: our palettes, font
pairings and the ten looks in kit/looks.css.

The model still decides. The brief narrows a menu of hundreds of options to a
handful that suit the user's industry, and its anti-patterns are the part a
model reliably gets wrong on its own.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from math import log
from typing import Any

from app.design import systems

# Our users build business dashboards, and upstream's 192 categories are
# mostly consumer apps and landing pages: matched freely, "attrition" lands on
# Sports Team/Club and "CSAT" on Autonomous Drone Fleet Manager. So the match is
# against business domains instead, each pointing at the upstream category
# whose rule fits it best. Earlier entries win ties. Words are matched after
# _stem, so plurals need no entry of their own.
_DOMAINS: tuple[tuple[str, str], ...] = (
    (
        "Job Board/Recruitment",  # upstream's "HR Analytics Dashboard"
        (
            "hr hiring hire recruit recruiter recruitment candidate applicant cv vacancy "
            "interview talent attrition headcount employee onboarding turnover workforce "
            "staff people retention"
        ),
    ),
    (
        "CRM & Client Management",  # "Sales Intelligence Dashboard"
        (
            "sale pipeline deal opportunity lead customer account churn quota rep crm "
            "support ticket csat nps satisfaction helpdesk renewal complaint"
        ),
    ),
    (
        "Invoice & Billing Tool",
        "invoice billing cash collection receivable payable overdue dunning payment",
    ),
    (
        "Financial Dashboard",
        (
            "budget actual forecast variance cost expense finance financial margin profit "
            "capex opex accounting"
        ),
    ),
    (
        "Marketing Agency",  # "Campaign Analytics"
        (
            "campaign marketing ad impression click ctr conversion content engagement seo "
            "social audience"
        ),
    ),
    (
        "Inventory & Stock Management",
        "inventory stock sku warehouse reorder supplier procurement purchasing vendor",
    ),
    (
        "Logistics/Delivery",
        "delivery shipment shipping carrier freight route fleet dispatch transport logistic",
    ),
    (
        "Analytics Dashboard",  # manufacturing has no category of its own
        (
            "production defect quality yield scrap oee downtime shift machine plant "
            "manufacturing throughput"
        ),
    ),
    (
        "Productivity Tool",  # "Drill-Down Analytics"
        "project portfolio milestone task sprint backlog deadline roadmap resourcing",
    ),
    (
        "LMS (Learning Management System)",
        "training course learning certification learner compliance completion",
    ),
    (
        "Sustainable Energy / Climate Tech",
        "energy kwh electricity consumption emission co2 carbon utility solar power",
    ),
    ("Healthcare App", "patient clinic hospital medical health care nurse"),
    ("Insurance Platform", "claim policy premium underwriting insurance"),
    (
        "Status Page / Incident Management",
        "incident outage uptime sla alert monitoring",
    ),
    ("E-commerce", "store shop retail ecommerce basket checkout"),
    ("Real Estate/Property", "property tenant lease rent occupancy"),
    ("Hotel/Hospitality", "hotel booking guest reservation"),
    ("Non-profit/Charity", "donation donor charity fundraising"),
    ("Educational App", "student school grade teacher"),
)

# Requirements that name no domain still describe a dashboard.
DEFAULT_CATEGORY = "Analytics Dashboard"

# Recommended fonts come from pairings upstream itself says suit business and
# data work; free scoring put "Kids/Education" on a compliance dashboard and
# "Kinetic Motion" on an energy one. Mobile-only and language-specific
# pairings are poor defaults for a desktop dashboard in English. The architect
# still sees, and may pick, every pairing.
_BUSINESS_FONTS = re.compile(
    r"dashboard|saas|enterprise|corporate|business|analytics|data|admin|financ|"
    r"professional|government|productivity|b2b",
    re.IGNORECASE,
)
_NOT_RECOMMENDED_FONTS = re.compile(
    r"mobile|system|hud|vietnamese|japanese|korean|chinese|arabic|thai|hebrew",
    re.IGNORECASE,
)

# Upstream style names (Style_Priority, Dashboard Style) to the look that
# implements them, or the nearest one. Styles with no dashboard equivalent
# (motion-driven, parallax, 3D, ...) map to nothing and are simply skipped.
_LOOK_FOR_STYLE = {
    "minimalism & swiss style": "minimalism-and-swiss-style",
    "swiss modernism 2.0": "minimalism-and-swiss-style",
    "exaggerated minimalism": "minimalism-and-swiss-style",
    "e-ink / paper": "minimalism-and-swiss-style",
    "flat design": "flat-design",
    "accessible & ethical": "flat-design",
    "inclusive design": "flat-design",
    "soft ui evolution": "soft-ui-evolution",
    "neumorphism": "soft-ui-evolution",
    "glassmorphism": "glassmorphism",
    "liquid glass": "glassmorphism",
    "claymorphism": "claymorphism",
    "aurora ui": "aurora-ui",
    "bento box grid": "bento-box-grid",
    "vibrant & block-based": "bento-box-grid",
    "data-dense dashboard": "data-dense-dashboard",
    "data-dense": "data-dense-dashboard",
    "real-time monitoring": "data-dense-dashboard",
    "heat map & heatmap style": "data-dense-dashboard",
    "financial dashboard": "data-dense-dashboard",
    "fluent 2": "fluent-2",
    "executive dashboard": "executive-dashboard",
}

_STOPWORD_TEXT = (
    "a an and are as at be by can for from has have how in into is it its of on or our "
    "so that the their them they this to us use used uses using via we what when which "
    "who will with without you your should must need needs want wants each every all "
    "per more most less than see show shows"
)
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def _tokens(text: str) -> list[str]:
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return [w for w in words if len(w) >= 2 and w not in _STOPWORDS]


class _BM25:
    """Okapi BM25 over a small corpus; the same scorer upstream uses."""

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = [Counter(_tokens(doc)) for doc in documents]
        self.lengths = [sum(doc.values()) for doc in self.docs]
        self.avgdl = (sum(self.lengths) / len(self.docs)) if self.docs else 1.0
        frequency: Counter[str] = Counter()
        for doc in self.docs:
            frequency.update(doc.keys())
        n = len(self.docs)
        self.idf = {t: log((n - f + 0.5) / (f + 0.5) + 1) for t, f in frequency.items()}

    def scores(self, query: str) -> list[float]:
        # Each distinct query word counts once: requirements repeat their
        # subject ("sales" six times), which would otherwise drown the rest.
        terms = [t for t in dict.fromkeys(_tokens(query)) if t in self.idf]
        out = []
        for doc, length in zip(self.docs, self.lengths, strict=True):
            score = 0.0
            for term in terms:
                tf = doc.get(term, 0)
                if tf:
                    norm = self.k1 * (1 - self.b + self.b * length / self.avgdl)
                    score += self.idf[term] * tf * (self.k1 + 1) / (tf + norm)
            out.append(score)
        return out


def _rows(name: str) -> list[dict[str, str]]:
    with (systems.DATA_DIR / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _stem(word: str) -> str:
    """Plural to singular, crudely: enough for "candidates" to match "candidate"."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


@lru_cache(maxsize=1)
def _domain_words() -> tuple[tuple[str, frozenset[str]], ...]:
    return tuple(
        (category, frozenset(_stem(w) for w in words.split())) for category, words in _DOMAINS
    )


def match_category(text: str) -> str:
    """The upstream category whose rule suits these requirements best.

    Scored by how often each domain's words occur, capped per word so one
    repeated subject cannot outvote everything else.
    """
    counts = Counter(_stem(token) for token in _tokens(text))
    best, best_score = DEFAULT_CATEGORY, 0
    for category, words in _domain_words():
        score = sum(min(counts[word], 3) for word in words)
        if score > best_score:
            best, best_score = category, score
    return best


@lru_cache(maxsize=1)
def _products() -> dict[str, dict[str, str]]:
    return {r["Product Type"].strip(): r for r in _rows("products.csv") if r.get("Product Type")}


@lru_cache(maxsize=1)
def _rules() -> dict[str, dict[str, str]]:
    return {r["UI_Category"].strip(): r for r in _rows("ui-reasoning.csv") if r.get("UI_Category")}


@lru_cache(maxsize=1)
def _font_candidates() -> tuple[tuple[systems.FontPairing, ...], _BM25]:
    eligible = tuple(
        p
        for p in systems.pairings()
        if _BUSINESS_FONTS.search(f"{p.best_for} {p.keywords}")
        and not _NOT_RECOMMENDED_FONTS.search(p.name)
        # Code fonts for headings read as a terminal, not a business report
        # (seen live: "Fira Code" titles on a quality dashboard).
        and not systems.is_code_font(p)
    )
    return eligible, _BM25([f"{p.name} {p.keywords} {p.best_for}" for p in eligible])


@lru_cache(maxsize=1)
def _palette_moods() -> tuple[tuple[str, ...], _BM25]:
    """Business categories with a usable palette, indexed by colour mood."""
    usable = {p.id for p in systems.palettes()}
    rules = _rules()
    categories = tuple(
        dict.fromkeys(c for c, _ in _DOMAINS if c in rules and systems.slug(c) in usable)
    )
    return categories, _BM25([rules[c].get("Color_Mood", "") for c in categories])


def _split(text: str) -> list[str]:
    return [part.strip() for part in (text or "").split("+") if part.strip()]


def _looks_for(names: list[str]) -> list[str]:
    looks = []
    for name in names:
        look = _LOOK_FOR_STYLE.get(name.strip().lower())
        if look and look not in looks:
            looks.append(look)
    return looks


@dataclass(frozen=True)
class DesignBrief:
    """What ui-ux-pro-max's rules recommend for one project's industry."""

    category: str | None
    looks: list[str] = field(default_factory=list)
    palettes: list[str] = field(default_factory=list)
    fonts: list[str] = field(default_factory=list)
    color_mood: str = ""
    typography_mood: str = ""
    key_effects: str = ""
    avoid: list[str] = field(default_factory=list)

    def for_prompt(self) -> dict[str, Any]:
        """The brief as the architect sees it: ids first, prose after."""
        if self.category is None:
            return {"category": None, "note": "No industry matched; choose freely."}
        return {
            "category": self.category,
            "recommendedStyles": self.looks,
            "recommendedPalettes": self.palettes,
            "recommendedFonts": self.fonts,
            "colorMood": self.color_mood,
            "typographyMood": self.typography_mood,
            "keyEffects": self.key_effects,
            "avoid": self.avoid,
        }


def _query_text(requirements: dict[str, Any]) -> str:
    """Everything a reader would use to tell what industry this is."""
    parts: list[str] = []
    for key, value in requirements.items():
        if key in ("theme", "dataset"):
            continue
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value if isinstance(item, str))
    dataset = requirements.get("dataset")
    if isinstance(dataset, dict):
        # Column names are strong industry signals: "patient_id", "kwh".
        for column in dataset.get("columns") or []:
            if isinstance(column, dict):
                parts.append(str(column.get("label") or column.get("key") or ""))
    return " ".join(parts)


def brief_for(requirements: dict[str, Any]) -> DesignBrief:
    """Match the requirements to an industry and read its design rule."""
    query = _query_text(requirements)
    category = match_category(query)
    product = _products().get(category, {})
    rule = _rules().get(category, {})
    if not rule:
        return DesignBrief(category=None)

    # Dashboard-specific advice first: Style_Priority is written for the whole
    # product, often its landing page, while this column is about dashboards.
    style_names = (
        _split(product.get("Dashboard Style (if applicable)", ""))
        + _split(rule.get("Style_Priority", ""))
        + [s.strip() for s in product.get("Secondary Styles", "").split(",")]
    )

    # The category's own palette, then the business categories whose colour
    # mood reads most alike — useful when its own was dropped as unreadable.
    usable = {p.id for p in systems.palettes()}
    palettes = [systems.slug(category)] if systems.slug(category) in usable else []
    categories, moods = _palette_moods()
    mood_scores = moods.scores(rule.get("Color_Mood", ""))
    for index in sorted(range(len(categories)), key=mood_scores.__getitem__, reverse=True):
        candidate = systems.slug(categories[index])
        if len(palettes) >= 3:
            break
        if candidate not in palettes:
            palettes.append(candidate)

    # The rule's mood and the category, not the whole brief: requirements are
    # full of words ("children", "luxury") that say nothing about type.
    pairings, fonts_index = _font_candidates()
    font_scores = fonts_index.scores(f"{rule.get('Typography_Mood', '')} {category}")
    ranked = sorted(range(len(pairings)), key=font_scores.__getitem__, reverse=True)
    fonts = [pairings[i].id for i in ranked[:3] if font_scores[i] > 0]

    return DesignBrief(
        category=category,
        looks=_looks_for(style_names),
        palettes=palettes,
        fonts=fonts,
        color_mood=rule.get("Color_Mood", "").strip(),
        typography_mood=rule.get("Typography_Mood", "").strip(),
        key_effects=rule.get("Key_Effects", "").strip(),
        avoid=_split(rule.get("Anti_Patterns", "")),
    )


def fill_design_system(chosen: Any, brief: DesignBrief) -> dict[str, str]:
    """The architect's designSystem, with gaps filled from the brief.

    A missing or unknown id would otherwise fall back to the platform default,
    which suits no one in particular; the brief's first pick suits the industry.
    """
    chosen = chosen if isinstance(chosen, dict) else {}
    known = {
        "palette": ({p.id for p in systems.palettes()}, brief.palettes),
        "fonts": ({p.id for p in systems.pairings()}, brief.fonts),
        "style": (set(systems.STYLES), brief.looks),
    }
    filled: dict[str, str] = {}
    for key, (valid, recommended) in known.items():
        value = chosen.get(key)
        if isinstance(value, str) and value in valid:
            filled[key] = value
        elif recommended:
            filled[key] = recommended[0]
    return filled
