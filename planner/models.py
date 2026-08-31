from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExperimentStep:
    actor: str
    purpose: str
    operation: str


@dataclass
class PlannedExperiment:
    hypothesis_id: str
    family: str
    priority: float
    steps: list[ExperimentStep] = field(default_factory=list)
    rationale: str = ""
