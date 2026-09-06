from dataclasses import dataclass, field

from violation.counterfactual import CounterfactualExperiment


@dataclass
class ExperimentCandidate:
    counterfactual: CounterfactualExperiment
    predictions: dict[str, str] = field(default_factory=dict)
    security_impact: float = 1.0
    setup_cost: float = 0.0

    @property
    def id(self) -> str:
        return self.counterfactual.hypothesis_id


@dataclass(frozen=True)
class ExperimentOutcome:
    candidate_id: str
    observed: str
    result: str
    evidence_id: str | None = None
