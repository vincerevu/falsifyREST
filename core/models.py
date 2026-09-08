from dataclasses import dataclass, field
from typing import Any


@dataclass
class Observation:
    status: int
    body: dict[str, Any] | str | None
    headers: dict[str, str]
    actor: str
    method: str
    endpoint: str
    extracted_ids: dict[str, Any] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    request_path: dict[str, Any] = field(default_factory=dict)
    request_query: dict[str, Any] = field(default_factory=dict)
    request_body: dict[str, Any] = field(default_factory=dict)
    objects_read: list[str] = field(default_factory=list)
    objects_created: list[str] = field(default_factory=list)
    objects_modified: list[str] = field(default_factory=list)
    state_before: dict[str, Any] = field(default_factory=dict)
    state_after: dict[str, Any] = field(default_factory=dict)

    @property
    def status_code(self) -> int:
        return self.status

    @property
    def response_body(self) -> dict[str, Any] | str | None:
        return self.body


@dataclass(frozen=True)
class Probe:
    id: str
    actor: str
    method: str
    path: str
    body: dict[str, Any] | None = None
    cost: float = 1.0
    risk: float = 0.0


@dataclass
class TraceStep:
    """One concrete request in an observed or candidate workflow."""
    probe: Probe
    observation: Observation | None = None
    bindings: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTrace:
    """A replayable workflow.  Search transforms this object, never a policy family."""
    id: str
    steps: list[TraceStep]

    @classmethod
    def from_probe(cls, probe: Probe) -> "ExecutionTrace":
        return cls(probe.id, [TraceStep(probe)])

    @property
    def probes(self) -> list[Probe]:
        return [step.probe for step in self.steps]


@dataclass
class Hypothesis:
    id: str
    phase: str
    actor_capabilities: dict[str, bool]
    ownership: dict[str, str] = field(default_factory=dict)
    previous_transition: str | None = None
    weight: float = 0.0
    evidence_support: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Prediction:
    status: int
    transition: str | None = None
    capability_allowed: bool | None = None

    def signature(self) -> tuple[int, str | None, bool | None]:
        return self.status, self.transition, self.capability_allowed


@dataclass
class TransitionEvidence:
    previous_phase: str
    action: str
    next_phase: str | None
