"""Risk scoring.

A risk score that cannot be explained is not usable. If someone asks why a vendor scored 68
rather than 40, "the model said so" ends the conversation badly — particularly when the
vendor is the one asking, and particularly when they are arguing about a renewal.

So scoring here is a weighted average with every step kept and returned:

    question risk    0–100, taken from the chosen answer option
    section score    weighted mean of its answered questions
    inherent risk    weighted mean of section scores
    residual risk    inherent risk adjusted for how much damage this vendor could do

The multiplier at the end is the part people argue about, so it is explicit rather than
buried: a careless vendor who touches nothing important is a smaller problem than a careless
vendor holding your customer database.
"""

import json
from typing import Dict, List, Optional

CRITICALITY_MULTIPLIER = {"low": 0.75, "medium": 1.0, "high": 1.25, "critical": 1.5}

BANDS = [(0, 25, "low"), (25, 50, "moderate"), (50, 75, "high"), (75, 101, "critical")]


def band_for(score: float) -> str:
    for lower, upper, label in BANDS:
        if lower <= score < upper:
            return label
    return "critical"


def score_assessment(
    definition_json: str, answers: Dict[str, str], criticality: str = "medium"
) -> dict:
    """Score answers against the questionnaire they were given.

    `definition_json` is the assessment's frozen snapshot, never the live template — that is
    what makes a score from last year reproducible today.
    """
    questions: List[dict] = json.loads(definition_json)

    sections: Dict[str, Dict[str, float]] = {}
    details: List[dict] = []
    unanswered: List[str] = []

    for question in questions:
        key = question["key"]
        section = question["section"]
        weight = float(question.get("weight", 1))
        sections.setdefault(section, {"weighted_risk": 0.0, "weight": 0.0})

        chosen = answers.get(key)
        if chosen is None:
            unanswered.append(key)
            continue

        option = next((o for o in question["options"] if o["label"] == chosen), None)
        if option is None:
            # An answer that is not one of the offered options cannot be scored. Treating it
            # as worst-case would be a silent judgement, so it is reported instead.
            unanswered.append(key)
            continue

        risk = float(option["risk"])
        sections[section]["weighted_risk"] += risk * weight
        sections[section]["weight"] += weight

        details.append(
            {
                "key": key,
                "section": section,
                "question": question["text"],
                "answer": chosen,
                "risk": risk,
                "weight": weight,
                "contribution": round(risk * weight, 2),
            }
        )

    section_scores = {
        name: round(values["weighted_risk"] / values["weight"], 1)
        for name, values in sections.items()
        if values["weight"] > 0
    }

    total_weight = sum(v["weight"] for v in sections.values())
    inherent = (
        round(sum(v["weighted_risk"] for v in sections.values()) / total_weight, 1)
        if total_weight
        else 0.0
    )

    multiplier = CRITICALITY_MULTIPLIER.get(criticality, 1.0)
    residual = round(min(inherent * multiplier, 100.0), 1)

    return {
        "inherent_risk": inherent,
        "residual_risk": residual,
        "band": band_for(residual),
        "criticality": criticality,
        "criticality_multiplier": multiplier,
        "answered": len(details),
        "total_questions": len(questions),
        "unanswered": unanswered,
        "section_scores": section_scores,
        # Highest-contributing answers first — the ones to raise with the vendor.
        "top_risks": sorted(details, key=lambda d: d["contribution"], reverse=True)[:5],
        "breakdown": details,
    }
