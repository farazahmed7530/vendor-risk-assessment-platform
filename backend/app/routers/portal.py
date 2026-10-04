"""The vendor's side.

Every endpoint here is addressed by token, never by assessment id. A vendor cannot
enumerate other assessments because they never learn an id, and the token is the only thing
that resolves to one. The internal routes and these routes deliberately share no path
prefix, so there is no way to drift into exposing one through the other.

Note what is *not* returned: no risk weights, no option scores, no other vendors. The
questionnaire is sent stripped of its scoring, because a vendor who can see that "No" scores
90 is being invited to answer the scoring rather than the question.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Answer, Assessment
from ..schemas import AnswersIn

router = APIRouter(prefix="/api/portal", tags=["vendor portal"])


def _load(token: str, db: Session) -> Assessment:
    assessment = db.execute(
        select(Assessment).where(Assessment.access_token == token)
    ).scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "This link is not valid")
    return assessment


@router.get("/{token}")
def open_questionnaire(token: str, db: Session = Depends(get_db)):
    assessment = _load(token, db)
    questions = json.loads(assessment.definition_snapshot)
    existing = {answer.question_key: answer for answer in assessment.answers}

    return {
        "vendor_name": assessment.vendor.name,
        "questionnaire": assessment.questionnaire_name,
        "status": assessment.status,
        "due_at": assessment.due_at,
        "submitted": assessment.status == "submitted",
        "questions": [
            {
                "key": question["key"],
                "section": question["section"],
                "text": question["text"],
                # Labels only — the risk value attached to each option stays internal.
                "options": [option["label"] for option in question["options"]],
                "answer": existing[question["key"]].value if question["key"] in existing else None,
                "note": existing[question["key"]].note if question["key"] in existing else "",
            }
            for question in questions
        ],
    }


@router.post("/{token}")
def save_answers(token: str, body: AnswersIn, db: Session = Depends(get_db)):
    """Save progress, or submit.

    Vendors fill these in over days, not minutes — usually by asking three colleagues. So
    saving is incremental and idempotent, and submitting is a separate, deliberate step.
    """
    assessment = _load(token, db)
    if assessment.status == "submitted":
        raise HTTPException(409, "This assessment has already been submitted")

    valid_keys = {question["key"] for question in json.loads(assessment.definition_snapshot)}
    existing = {answer.question_key: answer for answer in assessment.answers}

    for item in body.answers:
        if item.question_key not in valid_keys:
            raise HTTPException(400, f"Unknown question: {item.question_key}")

        if item.question_key in existing:
            existing[item.question_key].value = item.value
            existing[item.question_key].note = item.note
            existing[item.question_key].answered_at = datetime.now(timezone.utc)
        else:
            db.add(
                Answer(
                    assessment_id=assessment.id,
                    question_key=item.question_key,
                    value=item.value,
                    note=item.note,
                )
            )

    if body.submit:
        answered = {item.question_key for item in body.answers} | set(existing)
        missing = valid_keys - answered
        if missing:
            raise HTTPException(400, f"{len(missing)} question(s) still unanswered")
        assessment.status = "submitted"
        assessment.submitted_at = datetime.now(timezone.utc)
    elif assessment.status == "sent":
        assessment.status = "in_progress"

    db.commit()
    return {"status": assessment.status, "saved": len(body.answers)}
