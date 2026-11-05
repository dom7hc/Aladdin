"""Editable site content: the business cases offered as starting points and the
home page texts. JSON is camelCase like the rest of the API."""

from typing import Literal

from pydantic import Field

from app.schemas.project import CamelModel, NonEmptyText

# In step with app/generation/spec.py LAYOUTS; the layout steers the architect
# toward the arrangement that suits the problem.
Layout = Literal["kpi-overview", "analytics-breakdown", "records-workspace"]


class ScenarioInput(CamelModel):
    """A business case as an editor writes it."""

    title: NonEmptyText = Field(max_length=120)
    # Who it is for: the target users, in the reader's words.
    audience: NonEmptyText = Field(max_length=120)
    problem: NonEmptyText = Field(max_length=600)
    layout: Layout = "kpi-overview"
    highlights: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    # Seeds the requirement chat when a user picks this case.
    prompt: NonEmptyText = Field(max_length=1200)
    enabled: bool = True


class ScenarioResponse(ScenarioInput):
    id: str
    order: int
    builtin: bool = False


class ScenarioOrder(CamelModel):
    ids: list[str] = Field(min_length=1)


# The home page texts, defaulting to the wording the page shipped with. Every
# field is optional on save: a blank one falls back to its default.
HOME_DEFAULTS: dict[str, str] = {
    "badge": "Make your wish come true",
    "title": "Turn your idea into a",
    "title_highlight": "working dashboard",
    "subtitle": (
        "Describe the decision you need to make. You get a working dashboard and a "
        "slide deck to present it."
    ),
    "placeholder": "Which numbers do you need to see, and who needs to see them?",
    "scenarios_label": "Or start from one of these",
    "projects_title": "Recent Projects",
    "projects_subtitle": "Review specs, resume sessions, or launch live prototypes.",
}


class HomeContent(CamelModel):
    badge: str = Field(default=HOME_DEFAULTS["badge"], max_length=80)
    title: str = Field(default=HOME_DEFAULTS["title"], max_length=120)
    title_highlight: str = Field(default=HOME_DEFAULTS["title_highlight"], max_length=80)
    subtitle: str = Field(default=HOME_DEFAULTS["subtitle"], max_length=400)
    placeholder: str = Field(default=HOME_DEFAULTS["placeholder"], max_length=200)
    scenarios_label: str = Field(default=HOME_DEFAULTS["scenarios_label"], max_length=80)
    projects_title: str = Field(default=HOME_DEFAULTS["projects_title"], max_length=80)
    projects_subtitle: str = Field(default=HOME_DEFAULTS["projects_subtitle"], max_length=200)
