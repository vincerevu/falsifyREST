from dataclasses import dataclass, field

from core.models import Probe
from inference.hypothesis import PolicyHypothesis


@dataclass(frozen=True)
class CounterfactualExperiment:
    hypothesis_id: str
    family: str
    baseline: Probe
    intervention: Probe
    mutated_condition: str
    setup_probes: list[Probe] = field(default_factory=list)
    observation_probes: list[Probe] = field(default_factory=list)
    context: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CounterfactualContext:
    owner_id: str | None = None
    alternate_actor: str | None = None
    anonymous_actor: str | None = "anonymous"
    state: dict = field(default_factory=dict)
    history: dict[str, bool] = field(default_factory=dict)
    state_setup_probes: list[Probe] = field(default_factory=list)
    observation_probes: list[Probe] = field(default_factory=list)


class CounterfactualGenerator:
    """Create minimal one-variable changes from an observed successful seed probe."""
    def generate(self, hypothesis: PolicyHypothesis, baseline: Probe, context: CounterfactualContext) -> CounterfactualExperiment:
        if hypothesis.family == "ownership":
            if not context.alternate_actor:
                raise ValueError("ownership counterfactual requires an alternate actor")
            intervention = Probe(f"cf-{hypothesis.id}", context.alternate_actor, baseline.method, baseline.path, baseline.body, baseline.cost, baseline.risk)
            condition = "actor relation"
            setup = []
        elif hypothesis.family == "authorization":
            if not context.anonymous_actor:
                raise ValueError("authorization counterfactual requires an anonymous actor")
            intervention = Probe(f"cf-{hypothesis.id}", context.anonymous_actor, baseline.method, baseline.path, baseline.body, baseline.cost, baseline.risk)
            condition, setup = "authentication", []
        elif hypothesis.family == "replay":
            intervention = Probe(f"cf-{hypothesis.id}", baseline.actor, baseline.method, baseline.path, baseline.body, baseline.cost, baseline.risk)
            condition, setup = "action already executed", [baseline]
        else:
            if not context.state_setup_probes:
                raise ValueError("state counterfactual requires explicit setup probes for the alternative state")
            intervention = Probe(f"cf-{hypothesis.id}", baseline.actor, baseline.method, baseline.path, baseline.body, baseline.cost, baseline.risk)
            condition, setup = "state precondition", list(context.state_setup_probes)
        values = {"actor": {"id": intervention.actor, "authenticated": intervention.actor != context.anonymous_actor},
                  "resource": {"owner_id": context.owner_id}, "state": dict(context.state), "history": dict(context.history)}
        if hypothesis.family == "replay":
            values["history"][hypothesis.target_operation or hypothesis.action] = True
        return CounterfactualExperiment(hypothesis.id, hypothesis.family, baseline, intervention, condition, setup, list(context.observation_probes), values)
