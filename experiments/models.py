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

    @property
    def fingerprint(self) -> str:
        probe = self.counterfactual.intervention
        return "|".join([self.counterfactual.family, probe.actor, probe.method, probe.path, self.counterfactual.mutated_condition])


@dataclass(frozen=True)
class ExperimentOutcome:
    candidate_id: str
    observed: str
    result: str
    evidence_id: str | None = None
