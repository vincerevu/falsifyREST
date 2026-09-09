from dataclasses import dataclass, field
import json

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
        return self.fingerprint_for(self.counterfactual.context)

    def fingerprint_for(self, context: dict) -> str:
        probe = self.counterfactual.intervention
        payload = {
            "family": self.counterfactual.family, "actor": probe.actor, "method": probe.method, "path": probe.path,
            "condition": self.counterfactual.mutated_condition, "resource": context.get("resource", {}),
            "state": context.get("state", {}), "history": context.get("history", {}),
        }
        return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


@dataclass(frozen=True)
class ExperimentOutcome:
    candidate_id: str
    observed: str
    result: str
    evidence_id: str | None = None
    classification: str = "INCONCLUSIVE"
    witness: object | None = None
