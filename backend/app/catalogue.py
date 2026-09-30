"""The dashboards we offer to build.

Twenty scenarios that are genuinely useful to one role and genuinely buildable
from data that role already has. They serve three jobs:

* starting points a user can pick on the home page,
* guidance to the requirement agent about the shapes we do well,
* guidance to the architect about which layout suits which problem.

They steer rather than restrict: a user may describe something else and we
still build it. What they rule out is the open-ended "any app" promise the
product used to make — in particular chatbots and assistants, which we do not
build.

Each scenario names a role, a problem that role actually has, and a dashboard
that plausibly helps. Deliberately not detailed: the chat turns it into real
requirements, and a scenario that over-specifies would fight that.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Layouts must stay in step with app/generation/spec.py.
KPI = "kpi-overview"
ANALYTICS = "analytics-breakdown"
RECORDS = "records-workspace"


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    audience: str
    """The role whose problem this solves."""
    problem: str
    """What is hard for them today, in their words."""
    layout: str
    highlights: tuple[str, ...] = field(default=())
    """What the dashboard puts in front of them."""
    prompt: str = ""
    """Seeds the requirement chat when a user picks this scenario."""


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="cv-fit",
        title="Candidate fit screening",
        audience="Recruiter or hiring manager",
        problem=(
            "Every open role attracts dozens of CVs, and deciding who to "
            "shortlist means reading each one against the job description by hand."
        ),
        layout=RECORDS,
        highlights=(
            "Every candidate scored against the role's must-have skills",
            "Which requirements each candidate misses",
            "Filter by role, seniority and shortlist decision",
            "Years of experience and earliest start date side by side",
        ),
        prompt=(
            "A candidate fit dashboard for recruiters: score each applicant "
            "against a job description's required skills, show which "
            "requirements they miss, and let me filter by role and decision."
        ),
    ),
    Scenario(
        id="hiring-pipeline",
        title="Hiring pipeline health",
        audience="Talent acquisition lead",
        problem=(
            "Roles sit open for months and nobody can say which stage is the "
            "bottleneck or which hiring manager is slowest to give feedback."
        ),
        layout=ANALYTICS,
        highlights=(
            "Open roles and median days to hire",
            "Candidates in each stage, and where they drop out",
            "Time waiting on feedback per hiring manager",
        ),
        prompt=(
            "A hiring pipeline dashboard: open roles, median time to hire, how "
            "many candidates sit in each stage, and where candidates drop out."
        ),
    ),
    Scenario(
        id="attrition-watch",
        title="Attrition watch",
        audience="HR business partner",
        problem=(
            "Resignations are only noticed once they cluster, by which point "
            "the team is already short-staffed."
        ),
        layout=ANALYTICS,
        highlights=(
            "Leavers per month against headcount",
            "Turnover by team and by tenure band",
            "Teams trending worse than last quarter",
        ),
        prompt=(
            "An attrition dashboard for HR: leavers per month, turnover by team "
            "and tenure, and which teams are getting worse."
        ),
    ),
    Scenario(
        id="onboarding-progress",
        title="Onboarding progress",
        audience="People operations",
        problem=(
            "New joiners are chased for paperwork and equipment by email, and "
            "nobody has one view of who is actually ready to start."
        ),
        layout=RECORDS,
        highlights=(
            "Each joiner's outstanding steps before day one",
            "Overdue items by owner",
            "Filter by start week and department",
        ),
        prompt=(
            "An onboarding dashboard: each new joiner's outstanding steps "
            "before their start date, what is overdue, and who owns it."
        ),
    ),
    Scenario(
        id="sales-pipeline",
        title="Sales pipeline and forecast",
        audience="Sales manager",
        problem=(
            "The forecast lives in a spreadsheet that is stale by Monday, and "
            "nobody agrees which deals are really going to close."
        ),
        layout=KPI,
        highlights=(
            "Committed and weighted pipeline for the quarter",
            "Value by stage, and deals slipping past their close date",
            "Trend against target",
        ),
        prompt=(
            "A sales pipeline dashboard: total and weighted pipeline this "
            "quarter, value by stage, deals past their expected close date, and "
            "progress against target."
        ),
    ),
    Scenario(
        id="rep-performance",
        title="Rep performance",
        audience="Head of sales",
        problem=(
            "Coaching conversations are based on gut feel because per-rep "
            "numbers take a day to assemble."
        ),
        layout=ANALYTICS,
        highlights=(
            "Revenue and win rate per rep",
            "Average deal size and cycle length",
            "Activity against outcome, to show effort that is not converting",
        ),
        prompt=(
            "A rep performance dashboard: revenue and win rate per rep, average "
            "deal size, sales cycle length, and activity versus outcome."
        ),
    ),
    Scenario(
        id="churn-watch",
        title="Customer churn watch",
        audience="Customer success lead",
        problem=(
            "Accounts churn at renewal with no warning, even though usage had "
            "been falling for months."
        ),
        layout=KPI,
        highlights=(
            "Accounts at risk, ranked by revenue",
            "Usage trend for each at-risk account",
            "Renewals due in the next 90 days",
        ),
        prompt=(
            "A churn risk dashboard: which accounts are at risk ranked by "
            "revenue, their usage trend, and renewals due in the next 90 days."
        ),
    ),
    Scenario(
        id="support-load",
        title="Support workload",
        audience="Support team lead",
        problem=(
            "Queues spike without warning and the team finds out when customers "
            "start complaining about response times."
        ),
        layout=KPI,
        highlights=(
            "Open tickets, backlog age and first-response time",
            "Volume by channel over the week",
            "Tickets breaching their response target",
        ),
        prompt=(
            "A support workload dashboard: open tickets, backlog age, "
            "first-response time, volume by channel, and tickets breaching "
            "their response target."
        ),
    ),
    Scenario(
        id="csat-drivers",
        title="What drives satisfaction",
        audience="Customer experience manager",
        problem=(
            "The satisfaction score moves and nobody can say which issue types or teams moved it."
        ),
        layout=ANALYTICS,
        highlights=(
            "Satisfaction trend against ticket volume",
            "Score by issue category and by team",
            "The categories dragging the average down",
        ),
        prompt=(
            "A customer satisfaction dashboard: score trend over time, score by "
            "issue category and team, and which categories drag the average down."
        ),
    ),
    Scenario(
        id="campaign-spend",
        title="Campaign spend and return",
        audience="Marketing manager",
        problem=(
            "Budget is split across channels and agencies, and the cost per "
            "qualified lead is only known at the end of the quarter."
        ),
        layout=ANALYTICS,
        highlights=(
            "Spend and qualified leads per channel",
            "Cost per lead trend",
            "Campaigns above and below their target cost per lead",
        ),
        prompt=(
            "A campaign dashboard: spend and qualified leads per channel, cost "
            "per lead over time, and which campaigns beat their target."
        ),
    ),
    Scenario(
        id="content-performance",
        title="Content performance",
        audience="Content or product marketing",
        problem=(
            "Nobody knows which articles actually bring people who convert, so "
            "the content plan is guesswork."
        ),
        layout=RECORDS,
        highlights=(
            "Each piece with views, engaged time and conversions",
            "Filter by topic, author and publication month",
            "Best and worst performers side by side",
        ),
        prompt=(
            "A content performance dashboard: views, engaged time and "
            "conversions per article, filterable by topic and author."
        ),
    ),
    Scenario(
        id="budget-vs-actual",
        title="Budget versus actual",
        audience="Finance business partner",
        problem=(
            "Cost centre owners see their overspend a month late, in a report "
            "they have to read sideways."
        ),
        layout=ANALYTICS,
        highlights=(
            "Budget against actual by cost centre",
            "Variance trend month on month",
            "The largest overspends this period",
        ),
        prompt=(
            "A budget versus actual dashboard: spend against budget by cost "
            "centre, variance over time, and the biggest overspends."
        ),
    ),
    Scenario(
        id="cash-collections",
        title="Cash collections",
        audience="Credit control or finance",
        problem=(
            "Overdue invoices are chased from a spreadsheet, and the team "
            "cannot see which customers are quietly slipping."
        ),
        layout=RECORDS,
        highlights=(
            "Every open invoice with its age band",
            "Total overdue by customer",
            "Filter by age, owner and customer",
        ),
        prompt=(
            "A collections dashboard: open invoices by age band, total overdue "
            "per customer, and a filterable list of what to chase."
        ),
    ),
    Scenario(
        id="supplier-spend",
        title="Supplier spend",
        audience="Procurement lead",
        problem=(
            "Spend is spread across many suppliers with overlapping contracts, "
            "so negotiating leverage is invisible."
        ),
        layout=ANALYTICS,
        highlights=(
            "Spend by supplier and by category",
            "Spend trend against contract value",
            "Suppliers taking a growing share",
        ),
        prompt=(
            "A supplier spend dashboard: spend by supplier and category, trend "
            "over time, and which suppliers are taking a growing share."
        ),
    ),
    Scenario(
        id="inventory-health",
        title="Inventory health",
        audience="Supply chain planner",
        problem=(
            "Some lines sell out while others sit for a year, and both are only "
            "noticed after they hurt."
        ),
        layout=KPI,
        highlights=(
            "Lines at risk of stockout in the next month",
            "Slow movers and the cash tied up in them",
            "Stock cover trend",
        ),
        prompt=(
            "An inventory dashboard: which lines risk running out, which are "
            "slow moving and how much cash they tie up, and stock cover trend."
        ),
    ),
    Scenario(
        id="delivery-performance",
        title="Delivery performance",
        audience="Logistics manager",
        problem=(
            "Customers complain about late deliveries before the team can see a "
            "pattern by route or carrier."
        ),
        layout=ANALYTICS,
        highlights=(
            "On-time rate over time",
            "Late deliveries by route and by carrier",
            "Average delay where it is worst",
        ),
        prompt=(
            "A delivery performance dashboard: on-time rate over time, late "
            "deliveries by route and carrier, and where delays are worst."
        ),
    ),
    Scenario(
        id="production-quality",
        title="Production quality",
        audience="Production or quality manager",
        problem=(
            "Defects are counted at the end of the shift, so a drifting line "
            "runs for hours before anyone reacts."
        ),
        layout=ANALYTICS,
        highlights=(
            "Defect rate per line over the shift",
            "Defects by type and by line",
            "Lines above their tolerance",
        ),
        prompt=(
            "A production quality dashboard: defect rate per line over time, "
            "defects by type, and which lines are above tolerance."
        ),
    ),
    Scenario(
        id="project-portfolio",
        title="Project portfolio",
        audience="Programme or PMO lead",
        problem=(
            "Status comes from a dozen slide decks that disagree, and slippage "
            "surfaces at the steering meeting."
        ),
        layout=RECORDS,
        highlights=(
            "Every project with milestone progress and budget burn",
            "Which projects are late and by how much",
            "Filter by portfolio, owner and stage",
        ),
        prompt=(
            "A project portfolio dashboard: each project's milestone progress "
            "and budget burn, which are late, filterable by owner and stage."
        ),
    ),
    Scenario(
        id="training-compliance",
        title="Training compliance",
        audience="Learning and development, or compliance",
        problem=(
            "Mandatory training expiry is tracked in a spreadsheet, and audits "
            "turn into a scramble."
        ),
        layout=RECORDS,
        highlights=(
            "Who is overdue, per course",
            "Completion rate by department",
            "Certifications expiring in the next quarter",
        ),
        prompt=(
            "A training compliance dashboard: who is overdue per course, "
            "completion rate by department, and certifications expiring soon."
        ),
    ),
    Scenario(
        id="energy-usage",
        title="Energy and emissions",
        audience="Facilities or sustainability lead",
        problem=(
            "Energy bills arrive monthly with no way to tell which site or shift "
            "pattern caused a spike."
        ),
        layout=ANALYTICS,
        highlights=(
            "Consumption trend per site",
            "Usage and emissions by site and by meter",
            "Sites above their reduction target",
        ),
        prompt=(
            "An energy dashboard: consumption trend per site, usage and "
            "emissions by site, and which sites miss their reduction target."
        ),
    ),
)


BY_ID: dict[str, Scenario] = {scenario.id: scenario for scenario in SCENARIOS}


def as_public_list() -> list[dict[str, object]]:
    """Shape the home page offers as starting points."""
    return [
        {
            "id": s.id,
            "title": s.title,
            "audience": s.audience,
            "problem": s.problem,
            "highlights": list(s.highlights),
            "prompt": s.prompt,
        }
        for s in SCENARIOS
    ]


def prompt_guidance() -> str:
    """One line per scenario, for the agents' system prompts.

    Kept terse on purpose: the agents need the shape of what we build, not the
    full pitch, and a long list crowds out the rest of the instruction.
    """
    return "\n".join(f"- {s.title} ({s.audience}): {s.highlights[0]}" for s in SCENARIOS)
