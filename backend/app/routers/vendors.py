"""Internal endpoints — the security team's side."""

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Assessment, Answer, Questionnaire, Vendor
from ..schemas import VendorIn
from ..scoring import score_assessment

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


def _answers_map(assessment: Assessment) -> dict:
    return {answer.question_key: answer.value for answer in assessment.answers}


def _assessment_view(assessment: Assessment, criticality: str) -> dict:
    scored = score_assessment(
        assessment.definition_snapshot, _answers_map(assessment), criticality
    )
    return {
        "id": assessment.id,
        "status": assessment.status,
        "questionnaire": f"{assessment.questionnaire_name} v{assessment.questionnaire_version}",
        "sent_at": assessment.sent_at,
        "due_at": assessment.due_at,
        "submitted_at": assessment.submitted_at,
        "access_token": assessment.access_token,
        "reviewer_note": assessment.reviewer_note,
        "score": scored,
    }


@router.get("")
def list_vendors(db: Session = Depends(get_db)):
    vendors = db.execute(
        select(Vendor)
        .options(selectinload(Vendor.assessments).selectinload(Assessment.answers))
        .order_by(Vendor.name)
    ).scalars().all()

    out = []
    for vendor in vendors:
        latest = vendor.assessments[-1] if vendor.assessments else None
        out.append(
            {
                "id": vendor.id,
                "name": vendor.name,
                "service": vendor.service,
                "contact_email": vendor.contact_email,
                "criticality": vendor.criticality,
                "latest_assessment": _assessment_view(latest, vendor.criticality)
                if latest
                else None,
            }
        )
    return out


@router.post("", status_code=201)
def create_vendor(body: VendorIn, db: Session = Depends(get_db)):
    if db.execute(select(Vendor).where(Vendor.name == body.name)).scalar_one_or_none():
        raise HTTPException(409, "A vendor with that name already exists")

    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return {"id": vendor.id, "name": vendor.name}


@router.post("/{vendor_id}/assessments", status_code=201)
def send_assessment(vendor_id: int, due_in_days: int = 21, db: Session = Depends(get_db)):
    """Send a questionnaire, freezing its current definition into the assessment."""
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(404, "Vendor not found")

    questionnaire = db.execute(
        select(Questionnaire).order_by(Questionnaire.id.desc()).limit(1)
    ).scalar_one_or_none()
    if not questionnaire:
        raise HTTPException(400, "No questionnaire defined")

    assessment = Assessment(
        vendor_id=vendor.id,
        questionnaire_name=questionnaire.name,
        questionnaire_version=questionnaire.version,
        definition_snapshot=questionnaire.definition,
        due_at=datetime.now(timezone.utc) + timedelta(days=due_in_days),
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return {
        "id": assessment.id,
        "access_token": assessment.access_token,
        "vendor_link": f"/vendor/{assessment.access_token}",
        "questionnaire_version": assessment.questionnaire_version,
    }


@router.get("/{vendor_id}/assessments/{assessment_id}")
def assessment_detail(vendor_id: int, assessment_id: int, db: Session = Depends(get_db)):
    assessment = db.get(Assessment, assessment_id)
    if not assessment or assessment.vendor_id != vendor_id:
        raise HTTPException(404, "Assessment not found")

    vendor = assessment.vendor
    scored = score_assessment(
        assessment.definition_snapshot, _answers_map(assessment), vendor.criticality
    )
    questions = {q["key"]: q for q in json.loads(assessment.definition_snapshot)}

    return {
        "vendor": {"name": vendor.name, "criticality": vendor.criticality,
                   "service": vendor.service},
        "assessment": _assessment_view(assessment, vendor.criticality),
        "responses": [
            {
                "question": questions.get(answer.question_key, {}).get("text", answer.question_key),
                "section": questions.get(answer.question_key, {}).get("section", ""),
                "answer": answer.value,
                "note": answer.note,
                "evidence": answer.evidence_filename,
            }
            for answer in assessment.answers
        ],
        "score": scored,
    }
