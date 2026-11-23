"""Deterministic synthetic summaries, not records about real people/businesses.

Six complete months, a fixed date anchor, equal-weight team/cohort summaries,
and explicitly labelled sample targets. No random clock or model-created data.
The registry is used ONLY when no upload exists (enforced by preparation).
"""

from copy import deepcopy
from typing import Any

from app.catalogue import SCENARIOS
from app.generation.spec import normalize_spec

# field, label, unit, aggregation, lower-is-better, base, dimension, categories,
# later chart, rationale. New kinds themselves are implemented in T020–T022.
SAMPLE_CONFIGS = {
    "cv-fit": (
        "fit_score",
        "Candidate fit",
        "%",
        "mean",
        False,
        76,
        "role",
        ("Engineering", "Sales", "Finance", "Operations"),
        "heatmap",
        "Role by skill group; bounded scores, not additive stacks.",
    ),
    "hiring-pipeline": (
        "days_to_hire",
        "Time to hire",
        "days",
        "mean",
        True,
        48,
        "role",
        ("Engineering", "Sales", "Finance", "Operations"),
        "stage",
        "Stage backlog counts are independent; never infer cohort conversion.",
    ),
    "attrition-watch": (
        "attrition_rate",
        "Attrition rate",
        "%",
        "mean",
        True,
        8,
        "department",
        ("Engineering", "Sales", "Finance", "Operations"),
        "heatmap",
        "Department by tenure band; rates must never be stacked.",
    ),
    "onboarding-progress": (
        "completion",
        "Onboarding complete",
        "%",
        "mean",
        False,
        72,
        "team",
        ("Product", "Sales", "Finance", "Operations"),
        "bullet",
        "Completion against explicitly labelled sample target.",
    ),
    "sales-pipeline": (
        "pipeline_usd",
        "Pipeline value",
        "USD",
        "sum",
        False,
        32000,
        "stage",
        ("Prospect", "Qualified", "Proposal", "Negotiation"),
        "stage",
        "Independent stage values are not one conversion cohort.",
    ),
    "rep-performance": (
        "bookings_usd",
        "Bookings",
        "USD",
        "sum",
        False,
        24000,
        "rep",
        ("Alex", "Blair", "Casey", "Drew"),
        "bullet",
        "Bookings and sample quota share currency and period.",
    ),
    "churn-watch": (
        "churn_rate",
        "Customer churn",
        "%",
        "mean",
        True,
        6,
        "segment",
        ("Enterprise", "Business", "Small business", "Consumer"),
        "heatmap",
        "Segment by product; equal-weight cohort rates, not additive.",
    ),
    "support-load": (
        "open_tickets",
        "Open tickets",
        "tickets",
        "sum",
        True,
        46,
        "queue",
        ("Billing", "Technical", "Accounts", "General"),
        "stacked-bar",
        "Nonnegative ticket counts by queue/priority are additive.",
    ),
    "csat-drivers": (
        "satisfaction",
        "Satisfaction",
        "/5",
        "mean",
        False,
        3.7,
        "channel",
        ("Email", "Chat", "Phone", "Self-service"),
        "heatmap",
        "Channel by topic; average ratings are not additive.",
    ),
    "campaign-spend": (
        "spend_usd",
        "Campaign spend",
        "USD",
        "sum",
        True,
        4200,
        "channel",
        ("Search", "Social", "Email", "Events"),
        "bullet",
        "Spend against labelled sample budget, not invented ROI.",
    ),
    "content-performance": (
        "engaged_visits",
        "Engaged visits",
        "visits",
        "sum",
        False,
        3200,
        "format",
        ("Articles", "Video", "Guides", "Webinars"),
        "stacked-area",
        "Nonnegative visits by format over complete ordered months.",
    ),
    "budget-vs-actual": (
        "cost_usd",
        "Actual cost",
        "USD",
        "sum",
        True,
        8400,
        "cost_centre",
        ("Engineering", "Sales", "Finance", "Operations"),
        "bullet",
        "Actual cost and sample budget share currency and period.",
    ),
    "cash-collections": (
        "collected_usd",
        "Cash collected",
        "USD",
        "sum",
        False,
        13500,
        "region",
        ("North", "South", "East", "West"),
        "bullet",
        "Collections against sample target, not fictitious debt history.",
    ),
    "supplier-spend": (
        "spend_usd",
        "Supplier spend",
        "USD",
        "sum",
        True,
        7500,
        "supplier",
        ("Atlas", "Beacon", "Cedar", "Delta"),
        "stacked-bar",
        "Additive nonnegative spend by supplier and category.",
    ),
    "inventory-health": (
        "at_risk_skus",
        "At-risk SKUs",
        "SKUs",
        "sum",
        True,
        14,
        "warehouse",
        ("North", "South", "East", "West"),
        "heatmap",
        "Warehouse by product group exposes distinct risk counts.",
    ),
    "delivery-performance": (
        "on_time_rate",
        "On-time delivery",
        "%",
        "mean",
        False,
        88,
        "carrier",
        ("Atlas", "Beacon", "Cedar", "Delta"),
        "bullet",
        "Equal-size route cohorts; on-time rate vs sample target.",
    ),
    "production-quality": (
        "defect_rate",
        "Defect rate",
        "%",
        "mean",
        True,
        3.2,
        "line",
        ("Line A", "Line B", "Line C", "Line D"),
        "heatmap",
        "Line by shift, equal-sized batches; defect rates not stacked.",
    ),
    "project-portfolio": (
        "completion",
        "Milestones complete",
        "%",
        "mean",
        False,
        67,
        "project",
        ("Aurora", "Bridge", "Compass", "Discovery"),
        "bullet",
        "Project completion vs a labelled sample plan target.",
    ),
    "training-compliance": (
        "compliance",
        "Training compliance",
        "%",
        "mean",
        False,
        86,
        "team",
        ("Engineering", "Sales", "Finance", "Operations"),
        "heatmap",
        "Team by course; equal-sized cohorts and bounded rates.",
    ),
    "energy-usage": (
        "energy_kwh",
        "Energy used",
        "kWh",
        "sum",
        True,
        2400,
        "site",
        ("North", "South", "East", "West"),
        "stacked-area",
        "Nonnegative energy by site over complete ordered months.",
    ),
}


# Monthly shifts (May..October) and where the target sits relative to the
# middle category (positive: the target is harder to meet).
SAMPLE_SHAPES = (
    ((-0.10, -0.04, -0.08, -0.02, 0.0, 0.04), 0.02),  # rising, just short of target
    ((0.06, 0.04, 0.03, 0.0, -0.03, -0.05), -0.03),  # falling, still ahead of target
    ((0.02, -0.06, -0.09, -0.04, 0.0, 0.03), 0.01),  # dip and recovery
    ((-0.03, 0.02, -0.02, 0.03, -0.01, 0.01), -0.02),  # flat and choppy, on track
)


def aggregate_payloads(rows: list[dict], metric: dict) -> dict:
    """Also shipped verbatim into stub backends; every value derives from rows."""
    field = metric["field"]
    group_field = metric["dimension"]
    dates = sorted({r["date"] for r in rows})
    current = [r for r in rows if r["date"] == dates[-1]] if dates else []

    def value(items, key):
        numbers = [r[key] for r in items if isinstance(r.get(key), (int, float))]
        total = sum(numbers)
        return round(
            total / len(numbers) if metric["aggregation"] == "mean" and numbers else total, 4
        )

    breakdown = [
        {
            "label": group,
            "actual": value([r for r in current if r[group_field] == group], field),
            "target": value([r for r in current if r[group_field] == group], "sample_target"),
        }
        for group in dict.fromkeys(r[group_field] for r in current)
    ]
    series = [
        {
            "date": date,
            "actual": value([r for r in rows if r["date"] == date], field),
            "target": value([r for r in rows if r["date"] == date], "sample_target"),
        }
        for date in dates
    ]
    actual = value(current, field)
    return {
        "/api/metrics": {
            "actual": actual,
            "target": value(current, "sample_target"),
            "sampleCount": len(current),
            "total": actual,
        },
        "/api/breakdown": breakdown,
        "/api/series": series,
        "/api/records": [
            {**row, "variance": round(row["actual"] - row["target"], 4)} for row in breakdown
        ],
    }


def sample_for(scenario_id: str | None) -> dict[str, Any]:
    config = SAMPLE_CONFIGS.get(scenario_id)
    scenario = next((s for s in SCENARIOS if s.id == scenario_id), None)
    fixture_id = scenario_id if config else "generic"
    if config is None:
        config = (
            "activity_count",
            "Activities completed",
            "activities",
            "sum",
            False,
            72,
            "team",
            ("Product", "Sales", "Finance", "Operations"),
            "bullet",
            "A generic activity sample, not a claim about this custom idea.",
        )
    field, label, unit, aggregation, lower, base, dimension, groups, kind, reason = config
    metric = {
        "field": field,
        "label": label,
        "unit": unit,
        "aggregation": aggregation,
        "lowerIsBetter": lower,
        "dimension": dimension,
    }
    rows = []
    dates = ("2026-05-31", "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30", "2026-10-31")
    # A deterministic profile per starter, so sample dashboards do not all tell
    # the same story: its own trend shape, its own largest category, and a
    # target inside the spread so some categories meet it and some do not.
    profile = sum(map(ord, fixture_id)) % len(SAMPLE_SHAPES)
    shifts, target_offset = SAMPLE_SHAPES[profile]
    count = len(groups)
    middle = 0.86 + 0.025 + (count - 1) / 2 * 0.07 + shifts[-1]
    target = round(base * (middle - target_offset if lower else middle + target_offset), 2)
    for period, date in enumerate(dates):
        for group_index, group in enumerate(groups):
            rank = (group_index * 3 + profile) % count
            for segment in range(3):
                multiplier = 0.86 + rank * 0.07 + segment * 0.025 + shifts[period]
                actual = round(base * multiplier, 2)
                if unit == "/5":
                    actual = min(5, actual)
                if unit == "%":
                    actual = min(100, actual)
                if unit in ("tickets", "visits", "SKUs", "activities"):
                    actual = round(actual)
                rows.append(
                    {
                        "id": len(rows) + 1,
                        "date": date,
                        dimension: group,
                        "sample_segment": ("A", "B", "C")[segment],
                        field: actual,
                        "sample_target": target,
                    }
                )
    provenance = {
        "kind": "sample",
        "label": "Sample data",
        "fixtureId": fixture_id,
        "seed": 14,
        "dateAnchor": "2026-11-01",
    }
    comparison = {
        "kind": "target",
        "label": "Sample target",
        "endpoint": "/api/metrics",
        "field": "target",
        "unit": unit,
    }
    spec = normalize_spec(
        {
            "title": scenario.title if scenario else "Sample activity overview",
            "subtitle": "October 2026",
            "layout": scenario.layout if scenario else "kpi-overview",
            "provenance": provenance,
            "widgets": [
                {
                    "kind": "stat",
                    "label": label,
                    "endpoint": "/api/metrics",
                    "field": "actual",
                    "unit": unit,
                    "lowerIsBetter": lower,
                    "comparison": comparison,
                },
                {
                    "kind": "bar",
                    "title": f"{label} by {dimension.replace('_', ' ')}",
                    "endpoint": "/api/breakdown",
                    "categoryField": "label",
                    "unit": unit,
                    "series": [{"label": label, "field": "actual"}],
                    "comparison": {**comparison, "endpoint": "/api/breakdown", "keyField": "label"},
                },
                {
                    "kind": "line",
                    "title": f"{label} over complete months",
                    "endpoint": "/api/series",
                    "xField": "date",
                    "unit": unit,
                    "series": [{"label": label, "field": "actual"}],
                    "comparison": {**comparison, "endpoint": "/api/series", "keyField": "date"},
                },
                {
                    "kind": "table",
                    "title": f"October detail by {dimension.replace('_', ' ')}",
                    "endpoint": "/api/records",
                    "columns": [
                        {"label": dimension.replace("_", " ").title(), "field": "label"},
                        {"label": f"{label} ({unit})", "field": "actual"},
                        {"label": f"Sample target ({unit})", "field": "target"},
                        {
                            "label": "Variance (pp)" if unit == "%" else f"Variance ({unit})",
                            "field": "variance",
                        },
                    ],
                },
            ],
        }
    )
    return deepcopy(
        {
            "rows": rows,
            "metric": metric,
            "spec": spec,
            "provenance": provenance,
            "payloads": aggregate_payloads(rows, metric),
            "chartGuidance": {
                "kind": kind,
                "reason": reason,
                "dimension": dimension,
                "secondDimension": "sample_segment",
                "timeField": "date",
                "noConversionClaim": True,
            },
        }
    )
