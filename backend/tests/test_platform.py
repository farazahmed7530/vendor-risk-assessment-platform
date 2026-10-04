"""Tests aimed at the three things that would actually hurt in production:
scoring correctness, token isolation, and the questionnaire snapshot.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.scoring import score_assessment
from app.seed import seed


@pytest.fixture()
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with TestSession() as session:
        seed(session)

    def override():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


DEFINITION = json.dumps([
    {"key": "a", "section": "S1", "weight": 3, "text": "Q A",
     "options": [{"label": "Yes", "risk": 0}, {"label": "No", "risk": 100}]},
    {"key": "b", "section": "S1", "weight": 1, "text": "Q B",
     "options": [{"label": "Yes", "risk": 0}, {"label": "No", "risk": 100}]},
])


def test_weighting_actually_changes_the_score():
    heavy_bad = score_assessment(DEFINITION, {"a": "No", "b": "Yes"})
    light_bad = score_assessment(DEFINITION, {"a": "Yes", "b": "No"})
    assert heavy_bad["inherent_risk"] > light_bad["inherent_risk"]
    assert heavy_bad["inherent_risk"] == 75.0   # (100*3 + 0*1) / 4
    assert light_bad["inherent_risk"] == 25.0   # (0*3 + 100*1) / 4


def test_criticality_scales_residual_risk_but_not_inherent():
    answers = {"a": "No", "b": "Yes"}
    low = score_assessment(DEFINITION, answers, "low")
    critical = score_assessment(DEFINITION, answers, "critical")

    assert low["inherent_risk"] == critical["inherent_risk"]
    assert critical["residual_risk"] > low["residual_risk"]


def test_residual_risk_is_capped_at_100():
    worst = score_assessment(DEFINITION, {"a": "No", "b": "No"}, "critical")
    assert worst["residual_risk"] == 100.0


def test_unanswered_questions_are_reported_not_assumed():
    partial = score_assessment(DEFINITION, {"a": "Yes"})
    assert partial["unanswered"] == ["b"]
    assert partial["answered"] == 1


def test_an_unrecognised_answer_is_not_silently_scored():
    rubbish = score_assessment(DEFINITION, {"a": "Maybe", "b": "Yes"})
    assert "a" in rubbish["unanswered"]


def test_top_risks_lead_with_the_biggest_contributor():
    scored = score_assessment(DEFINITION, {"a": "No", "b": "No"})
    assert scored["top_risks"][0]["key"] == "a"


def test_the_portal_never_exposes_option_risk_values(client):
    vendors = client.get("/api/vendors").json()
    token = vendors[0]["latest_assessment"]["access_token"]

    body = client.get(f"/api/portal/{token}").json()
    serialised = json.dumps(body)

    assert '"risk"' not in serialised, "scoring must not leak to the vendor"
    assert all(isinstance(option, str) for q in body["questions"] for option in q["options"])


def test_a_token_resolves_only_to_its_own_assessment(client):
    vendors = client.get("/api/vendors").json()
    first, second = vendors[0], vendors[1]

    body = client.get(f"/api/portal/{first['latest_assessment']['access_token']}").json()
    assert body["vendor_name"] == first["name"]
    assert body["vendor_name"] != second["name"]


def test_an_invalid_token_is_rejected(client):
    assert client.get("/api/portal/not-a-real-token").status_code == 404


def test_answers_save_incrementally_then_submit(client):
    vendors = client.get("/api/vendors").json()
    token = vendors[0]["latest_assessment"]["access_token"]
    questions = client.get(f"/api/portal/{token}").json()["questions"]

    half = [{"question_key": q["key"], "value": q["options"][0]} for q in questions[:4]]
    assert client.post(f"/api/portal/{token}", json={"answers": half}).json()["status"] == "in_progress"

    # Submitting while incomplete is refused.
    assert client.post(f"/api/portal/{token}", json={"answers": [], "submit": True}).status_code == 400

    rest = [{"question_key": q["key"], "value": q["options"][0]} for q in questions[4:]]
    assert client.post(f"/api/portal/{token}", json={"answers": rest, "submit": True}).json()["status"] == "submitted"

    # And it cannot be submitted twice.
    assert client.post(f"/api/portal/{token}", json={"answers": []}).status_code == 409


def test_editing_the_questionnaire_does_not_change_a_sent_assessment(client):
    """The snapshot is the point: a score reported last quarter must still reproduce."""
    vendors = client.get("/api/vendors").json()
    vendor_id = vendors[0]["id"]
    assessment_id = vendors[0]["latest_assessment"]["id"]

    before = client.get(f"/api/vendors/{vendor_id}/assessments/{assessment_id}").json()
    original_total = before["score"]["total_questions"]

    # Simulate the questionnaire being revised afterwards.
    from app.models import Questionnaire
    from sqlalchemy import select

    session = next(app.dependency_overrides[get_db]())
    questionnaire = session.execute(select(Questionnaire)).scalars().first()
    questionnaire.definition = json.dumps(json.loads(questionnaire.definition)[:3])
    session.commit()

    after = client.get(f"/api/vendors/{vendor_id}/assessments/{assessment_id}").json()
    assert after["score"]["total_questions"] == original_total
