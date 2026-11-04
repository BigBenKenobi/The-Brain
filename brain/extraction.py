"""Extension contract for future opt-in semantic extraction.

Adapters must receive only bounded, already screened evidence. Implementations
must validate returned source spans, never elevate evidence status without proof,
and report provider/model identity and measurable usage. No network adapter ships.
"""
from typing import Protocol, TypedDict

class ExtractionInput(TypedDict):
    project_id: str
    path: str
    sha256: str
    text: str

class ExtractionResult(TypedDict):
    records: list[dict]
    model: str | None
    usage: dict
    limitations: list[str]

class Extractor(Protocol):
    identity: str
    def available(self) -> bool: ...
    def extract(self, evidence: ExtractionInput) -> ExtractionResult: ...
