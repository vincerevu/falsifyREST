from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExperimentStep:
    actor: str
    purpose: str
    operation: str


@dataclass(frozen=True)
class ExecutableStep:
    operation_id: str
    actor_id: str
    method: str
    path_template: str
    path_bindings: dict[str, str] = field(default_factory=dict)
    body_bindings: dict[str, Any] = field(default_factory=dict)
    purpose: str = ""
    probe: object | None = None


@dataclass
class ExperimentPlan:
    hypothesis_id: str
    setup_steps: list[ExecutableStep] = field(default_factory=list)
    intervention_step: ExecutableStep | None = None
    observation_steps: list[ExecutableStep] = field(default_factory=list)
    mutated_condition: str = ""


@dataclass
class PlannedExperiment:
    hypothesis_id: str
    family: str
    priority: float
    steps: list[ExperimentStep] = field(default_factory=list)
    rationale: str = ""
