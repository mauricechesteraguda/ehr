"""type-10022026-Maurice: Explicit terminology seam; only deterministic fixtures ship."""
from dataclasses import dataclass
from .logging import log_event

SYNTHETIC_SNOMED = "http://snomed.info/sct"


@dataclass(frozen=True)
class Concept:
    system: str
    code: str
    display: str
    version: str


class TerminologyUnavailable(Exception):
    """Terminology dependency cannot establish a validation result."""


class TerminologyAdapter:
    """type-10022026-Maurice: Interface boundary for licensed terminology services."""
    def validate(self, *, system: str, code: str, display: str) -> Concept:
        raise NotImplementedError


class SyntheticFixtureTerminologyAdapter(TerminologyAdapter):
    """Synthetic subset only; no SNOMED content is redistributed."""
    concepts = {"IHD-001": "Synthetic ischemic heart disease", "SNOMED-002": "Synthetic family condition"}

    def validate(self, *, system: str, code: str, display: str) -> Concept:
        if not system or not code or not display or not system.startswith("http"):
            raise ValueError("A terminology system URI, code, and display are required.")
        expected = self.concepts.get(code)
        if expected is None:
            raise ValueError("Concept is not in the approved synthetic fixture subset.")
        if display != expected:
            raise ValueError("Concept display does not match the approved fixture.")
        result = Concept(system=system, code=code, display=display, version="synthetic-2026-01")
        log_event("terminology.validate", component="terminology", operation="validate", outcome="success", duration_ms=0)
        return result


adapter: TerminologyAdapter = SyntheticFixtureTerminologyAdapter()
