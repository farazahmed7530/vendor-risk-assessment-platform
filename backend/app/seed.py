"""A real-ish security questionnaire and two vendors, so the app is usable immediately."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Assessment, Questionnaire, Vendor

YES_NO = lambda yes_risk, no_risk: [  # noqa: E731
    {"label": "Yes", "risk": yes_risk},
    {"label": "No", "risk": no_risk},
]

QUESTIONS = [
    {"key": "soc2", "section": "Certifications", "weight": 3,
     "text": "Do you hold a current SOC 2 Type II report?",
     "options": [{"label": "Yes", "risk": 0}, {"label": "In progress", "risk": 45},
                 {"label": "No", "risk": 85}]},
    {"key": "pentest", "section": "Certifications", "weight": 2,
     "text": "Is an independent penetration test carried out at least annually?",
     "options": YES_NO(5, 70)},
    {"key": "mfa", "section": "Access Control", "weight": 3,
     "text": "Is multi-factor authentication enforced for all staff with production access?",
     "options": YES_NO(0, 90)},
    {"key": "offboarding", "section": "Access Control", "weight": 2,
     "text": "Is access revoked within one business day of someone leaving?",
     "options": [{"label": "Yes", "risk": 5}, {"label": "Within a week", "risk": 40},
                 {"label": "No defined process", "risk": 95}]},
    {"key": "encryption_rest", "section": "Data Protection", "weight": 3,
     "text": "Is customer data encrypted at rest?",
     "options": YES_NO(0, 95)},
    {"key": "subprocessors", "section": "Data Protection", "weight": 2,
     "text": "Do you maintain a published list of subprocessors with access to customer data?",
     "options": YES_NO(10, 60)},
    {"key": "retention", "section": "Data Protection", "weight": 2,
     "text": "Is data deleted within 30 days of a customer request?",
     "options": [{"label": "Yes", "risk": 0}, {"label": "Within 90 days", "risk": 35},
                 {"label": "No defined process", "risk": 90}]},
    {"key": "incident_sla", "section": "Incident Response", "weight": 3,
     "text": "Will you notify customers of a breach within 72 hours?",
     "options": [{"label": "Yes, contractually", "risk": 0},
                 {"label": "Best effort", "risk": 50},
                 {"label": "No commitment", "risk": 95}]},
    {"key": "incident_tested", "section": "Incident Response", "weight": 2,
     "text": "Has your incident response plan been exercised in the last 12 months?",
     "options": YES_NO(5, 65)},
    {"key": "bcp", "section": "Resilience", "weight": 2,
     "text": "Are backups tested by performing an actual restore at least annually?",
     "options": YES_NO(5, 75)},
]


def seed(db: Session) -> bool:
    if db.execute(select(Vendor).limit(1)).scalar_one_or_none():
        return False

    definition = json.dumps(QUESTIONS)
    questionnaire = Questionnaire(
        name="Security & Data Protection Review", version=1, definition=definition
    )
    db.add(questionnaire)

    vendors = [
        Vendor(name="Northwind Analytics", contact_email="security@northwind.example",
               service="Product analytics — receives pseudonymised event data",
               criticality="medium"),
        Vendor(name="Harbour Payments", contact_email="compliance@harbourpay.example",
               service="Payment processing — holds cardholder data", criticality="critical"),
        Vendor(name="Clearwater Mail", contact_email="ops@clearwatermail.example",
               service="Transactional email delivery", criticality="low"),
    ]
    for vendor in vendors:
        db.add(vendor)
    db.flush()

    for vendor in vendors:
        db.add(
            Assessment(
                vendor_id=vendor.id,
                questionnaire_name=questionnaire.name,
                questionnaire_version=questionnaire.version,
                definition_snapshot=definition,
                due_at=datetime.now(timezone.utc) + timedelta(days=21),
            )
        )

    db.commit()
    return True
