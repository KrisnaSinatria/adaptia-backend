"""Skema respons. JSON keluar dalam camelCase persis seperti src/lib/data.ts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Status = Literal["terpenuhi", "sebagian", "belum", "ambigu"]
Stage = Literal["praktik", "reverse_tutor", "penerapan"]
Decision = Literal["accept", "correct", "reject"]


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
