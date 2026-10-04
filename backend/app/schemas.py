from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class VendorIn(BaseModel):
    name: str
    contact_email: str
    service: str = ""
    criticality: str = "medium"


class AnswerIn(BaseModel):
    question_key: str
    value: str
    note: str = ""


class AnswersIn(BaseModel):
    answers: List[AnswerIn]
    submit: bool = False


class AssessmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    due_at: datetime
    submitted_at: Optional[datetime] = None
    questionnaire_name: str
    questionnaire_version: int
    access_token: str
