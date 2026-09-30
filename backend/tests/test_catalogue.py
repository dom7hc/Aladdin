"""The dashboards we offer to build."""

import re

from app.catalogue import BY_ID, SCENARIOS, as_public_list, prompt_guidance
from app.generation.spec import LAYOUTS

# Things this product does not build. The home page used to advertise "a support
# assistant that answers HR policy questions", which is exactly what one user's
# requirements then became.
NOT_OFFERED = ("chatbot", "chat bot", "assistant", "wizard", "q&a", "question-and-answer")


def test_twenty_scenarios_with_unique_ids():
    assert len(SCENARIOS) == 20
    assert len(BY_ID) == 20


def test_every_scenario_is_complete():
    for scenario in SCENARIOS:
        assert scenario.title.strip()
        assert scenario.audience.strip(), f"{scenario.id} names no role"
        assert scenario.problem.strip(), f"{scenario.id} states no problem"
        assert scenario.highlights, f"{scenario.id} shows nothing"
        assert scenario.prompt.strip(), f"{scenario.id} cannot seed the chat"


def test_every_scenario_uses_a_layout_we_can_render():
    """A scenario naming a retired layout would fail at the architect step."""
    for scenario in SCENARIOS:
        assert scenario.layout in LAYOUTS, f"{scenario.id} wants {scenario.layout}"


def test_no_scenario_offers_something_we_do_not_build():
    for scenario in SCENARIOS:
        haystack = " ".join(
            [scenario.title, scenario.problem, scenario.prompt, *scenario.highlights]
        ).lower()
        for term in NOT_OFFERED:
            assert term not in haystack, f"{scenario.id} offers a {term}"


def test_scenarios_name_a_role_not_a_technology():
    """Each one must be somebody's problem, not a feature list."""
    for scenario in SCENARIOS:
        # A problem statement reads as a sentence about people.
        assert len(scenario.problem.split()) >= 8, f"{scenario.id}'s problem is too thin"


def test_the_offering_spans_more_than_one_department():
    """Twenty variations on sales would not be a catalogue."""
    audiences = {s.audience.lower() for s in SCENARIOS}
    assert len(audiences) >= 15


def test_public_list_is_serialisable_and_complete():
    public = as_public_list()
    assert len(public) == 20
    first = public[0]
    assert set(first) == {"id", "title", "audience", "problem", "highlights", "prompt"}
    assert isinstance(first["highlights"], list)


def test_prompt_guidance_is_one_terse_line_per_scenario():
    """It goes inside a system prompt, so it must not crowd out the rest."""
    lines = prompt_guidance().splitlines()
    assert len(lines) == 20
    assert all(line.startswith("- ") for line in lines)
    assert not re.search(r"\n\n", prompt_guidance())
    assert len(prompt_guidance()) < 3000


def test_the_hr_example_the_feedback_asked_for_exists():
    """'HR has a CV dashboard to see whether candidates fit the job description.'"""
    cv = BY_ID["cv-fit"]
    assert "candidate" in cv.title.lower()
    assert "recruiter" in cv.audience.lower() or "hiring" in cv.audience.lower()
    assert "job description" in cv.prompt.lower()
