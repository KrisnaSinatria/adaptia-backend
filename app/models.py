"""Skema permintaan dan respons. JSON memakai camelCase persis seperti src/lib/data.ts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Status = Literal["terpenuhi", "sebagian", "belum", "ambigu"]
Stage = Literal["praktik", "reverse_tutor", "penerapan"]
Decision = Literal["accept", "correct", "reject"]

# Batas panjang per jawaban supaya prompt dan biaya LLM tetap terkendali.
MAX_TEXT = 4000


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Indicator(CamelModel):
    id: str
    name: str
    concept: str | None = None
    weight: int


class SessionDetail(CamelModel):
    id: str
    title: str
    instruction: str | None = None
    goal: str | None = None
    indicators: list[Indicator]
    penerapan: list = []


class PracticeIn(CamelModel):
    code: str = Field(default="", max_length=MAX_TEXT)
    explain: str = Field(default="", max_length=MAX_TEXT)


class BobyTurnIn(CamelModel):
    text: str | None = Field(default=None, max_length=MAX_TEXT)
    choice: Literal["Setuju", "Tidak setuju"] | None = None


class ApplicationIn(CamelModel):
    answers: list[Annotated[str, Field(max_length=MAX_TEXT)]] = Field(min_length=1, max_length=10)


class DecisionIn(CamelModel):
    indicator: str
    decision: Decision
    status: Status | None = None


class FinalizeIn(CamelModel):
    note: str = Field(default="", max_length=MAX_TEXT)


class AssignmentIn(CamelModel):
    activity_id: str
    student_ids: list[str] = Field(min_length=1)
    start: str = Field(max_length=100)
    due: str = Field(max_length=100)
    mode: str = Field(max_length=50)
