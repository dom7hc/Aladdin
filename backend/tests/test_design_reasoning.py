"""ui-ux-pro-max's design reasoning, run on the server for the architect."""

import pytest

from app.catalogue import SCENARIOS
from app.design import reasoning, systems


def _requirements(problem: str, **extra) -> dict:
    return {"problem": problem, **extra}


@pytest.mark.parametrize(
    ("problem", "category"),
    [
        ("Track attrition and headcount by department", "Job Board/Recruitment"),
        ("Sales pipeline by stage and rep quota attainment", "CRM & Client Management"),
        ("Overdue invoices and cash collections", "Invoice & Billing Tool"),
        ("Budget versus actual cost per cost centre", "Financial Dashboard"),
        ("Defect rate per production line and shift", "Analytics Dashboard"),
        ("Energy consumption in kWh per site", "Sustainable Energy / Climate Tech"),
        ("On-time delivery per carrier and route", "Logistics/Delivery"),
        ("Stock levels and reorder points per warehouse", "Inventory & Stock Management"),
    ],
)
def test_business_briefs_land_on_a_fitting_category(problem: str, category: str):
    assert reasoning.brief_for(_requirements(problem)).category == category


def test_free_bm25_misfits_stay_fixed():
    """Observed before the domain table: matched freely against upstream's
    consumer-heavy catalogue, attrition landed on Sports Team/Club and CSAT on
    Autonomous Drone Fleet Manager."""
    attrition = reasoning.brief_for(_requirements("Who is likely to leave: attrition risk"))
    assert attrition.category == "Job Board/Recruitment"
    csat = reasoning.brief_for(_requirements("CSAT drivers from support ticket surveys"))
    assert csat.category == "CRM & Client Management"


def test_requirements_naming_no_domain_still_get_dashboard_rules():
    brief = reasoning.brief_for(_requirements("Something about widgets"))
    assert brief.category == reasoning.DEFAULT_CATEGORY
    assert brief.looks


def test_dataset_columns_count_as_signals():
    requirements = {
        "problem": "Weekly overview",
        "dataset": {"columns": [{"key": "kwh", "label": "Energy kWh"}]},
    }
    assert reasoning.brief_for(requirements).category == "Sustainable Energy / Climate Tech"


def test_every_recommendation_is_an_id_the_platform_can_use():
    """The brief is only useful in ids the architect can actually pick."""
    looks = set(systems.STYLES)
    palettes = {p.id for p in systems.palettes()}
    pairings = {p.id for p in systems.pairings()}
    for scenario in SCENARIOS:
        brief = reasoning.brief_for(
            {"problem": scenario.problem, "features": list(scenario.highlights)}
        )
        assert brief.category, scenario.id
        assert brief.looks and set(brief.looks) <= looks, scenario.id
        assert brief.palettes and set(brief.palettes) <= palettes, scenario.id
        assert brief.fonts and set(brief.fonts) <= pairings, scenario.id


def test_recommended_fonts_suit_a_business_dashboard():
    """Free scoring once put Kids/Education on a compliance dashboard."""
    for scenario in SCENARIOS:
        brief = reasoning.brief_for({"problem": scenario.problem})
        assert not any("kids" in font or "mobile" in font for font in brief.fonts)


def test_brief_for_prompt_carries_the_anti_patterns():
    brief = reasoning.brief_for(_requirements("Sales pipeline by stage"))
    prompt = brief.for_prompt()
    assert prompt["category"] == "CRM & Client Management"
    assert "Excessive decoration" in prompt["avoid"]
    assert prompt["recommendedStyles"][0] in systems.STYLES


def test_fill_design_system_keeps_valid_choices_and_fills_gaps():
    brief = reasoning.brief_for(_requirements("Sales pipeline by stage"))
    filled = reasoning.fill_design_system({"palette": "made-up", "style": "glassmorphism"}, brief)
    assert filled["style"] == "glassmorphism"
    assert filled["palette"] == brief.palettes[0]
    assert filled["fonts"] == brief.fonts[0]


def test_fill_design_system_tolerates_a_malformed_choice():
    brief = reasoning.brief_for(_requirements("Sales pipeline"))
    assert reasoning.fill_design_system("nonsense", brief)["style"] == brief.looks[0]
