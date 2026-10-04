"""Schema.

Two decisions shape everything here.

**1. An assessment snapshots its questionnaire.**
Templates get edited — questions reworded, weights tuned, sections added. If an assessment
pointed at a live template, last year's risk score would silently change whenever someone
adjusted a weight, and you could never reproduce the number you reported to the board. So
the questionnaire is copied into the assessment at send time and frozen there.

**2. Vendors have no accounts.**
An external supplier is not going to create a login to fill in your questionnaire. Each
assessment carries a long random token; the vendor gets a link containing it, and that token
scopes them to exactly one assessment. No password to reset, nothing to deprovision later.
"""

import secrets
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_token() -> str:
    return secrets.token_urlsafe(32)


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(190), unique=True)
    contact_email: Mapped[str] = mapped_column(String(190))
    service: Mapped[str] = mapped_column(String(255), default="")
    # How much damage this vendor could do if it failed or was breached.
    criticality: Mapped[str] = mapped_column(String(16), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assessments: Mapped[List["Assessment"]] = relationship(
        back_populates="vendor", cascade="all, delete-orphan", order_by="Assessment.id"
    )


class Questionnaire(Base):
    """The editable master. Assessments never read from this after they are sent."""

    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(190))
    version: Mapped[int] = mapped_column(Integer, default=1)
    # [{key, section, text, weight, options:[{label, risk}]}]
    definition: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    questionnaire_name: Mapped[str] = mapped_column(String(190))
    questionnaire_version: Mapped[int] = mapped_column(Integer)
    # Frozen copy of the questionnaire definition as it stood when this was sent.
    definition_snapshot: Mapped[str] = mapped_column(Text)
    access_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=new_token)
    status: Mapped[str] = mapped_column(String(24), default="sent")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_note: Mapped[str] = mapped_column(Text, default="")

    vendor: Mapped[Vendor] = relationship(back_populates="assessments")
    answers: Mapped[List["Answer"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    question_key: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[str] = mapped_column(String(190))
    note: Mapped[str] = mapped_column(Text, default="")
    evidence_filename: Mapped[str] = mapped_column(String(255), default="")
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assessment: Mapped[Assessment] = relationship(back_populates="answers")
