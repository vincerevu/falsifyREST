from dataclasses import dataclass

from core.models import Probe
from inference.hypothesis import PolicyHypothesis


@dataclass(frozen=True)
class CounterfactualExperiment:
    hypothesis_id: str
    family: str
    baseline: Probe
    intervention: Probe
    mutated_condition: str


class CounterfactualGenerator:
    """Create minimal one-variable changes from an observed successful seed probe."""
    def generate(self, hypothesis: PolicyHypothesis, baseline: Probe, alternate_actor: str | None = None) -> CounterfactualExperiment:
        if hypothesis.family == "ownership":
            if not alternate_actor:
                raise ValueError("ownership counterfactual requires an alternate actor")
            intervention = Probe(f"cf-{hypothesis.id}", alternate_actor, baseline.method, baseline.path, baseline.body, baseline.cost, baseline.risk)
            condition = "actor relation"
        elif hypothesis.family == "replay":
            intervention = Probe(f"cf-{hypothesis.id}", baseline.actor, baseline.method, baseline.path, baseline.body, baseline.cost, baseline.risk)
            condition = "action already executed"
        else:
            intervention = Probe(f"cf-{hypothesis.id}", baseline.actor, baseline.method, baseline.path, baseline.body, baseline.cost, baseline.risk)
            condition = "state precondition"
        return CounterfactualExperiment(hypothesis.id, hypothesis.family, baseline, intervention, condition)
