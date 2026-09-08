from dataclasses import dataclass, field

from core.models import ExecutionTrace, Probe
from evidence.context import EvaluationContext
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
    alternate_resource_path: str | None = None


class CounterfactualGenerator:
    """Legacy adapter over generic trace transformations.

    New code should use ``search.CounterexampleSearchEngine`` directly.  Keeping
    this adapter preserves callers that still expect one experiment candidate.
    """
    def generate(self, hypothesis: PolicyHypothesis, baseline: Probe, context: CounterfactualContext) -> CounterfactualExperiment:
        from search.operators import ActorSwap, OmitStep, Repeat, ResourceSwap

        seed = ExecutionTrace.from_probe(baseline)
        operators = [ActorSwap(), ResourceSwap(), Repeat(), OmitStep()]
        # This compatibility shim supplies an explicit state prefix only to the
        # omission operator.  The search engine itself always receives a full
        # observed trace and does not branch on family.
        if hypothesis.family == "state-transition" and context.state_setup_probes:
            from core.models import TraceStep
            seed = ExecutionTrace(baseline.id, [*(TraceStep(probe) for probe in context.state_setup_probes), *seed.steps])
            operators = [OmitStep(), Repeat(), ActorSwap(), ResourceSwap()]
        elif hypothesis.family == "replay":
            operators = [Repeat(), ActorSwap(), ResourceSwap(), OmitStep()]
        available = [operator for operator in operators if hypothesis.is_applicable_operator(operator) and operator.applicable(hypothesis, seed, context)]
        if not available:
            raise ValueError("no applicable trace transformation for hypothesis and seed")
        operator = available[0]
        # A legacy state experiment already receives its alternative workflow
        # from the adapter as explicit setup; preserve that concrete seed.
        trace = seed if hypothesis.family == "state-transition" else operator.apply(seed, context)
        intervention = trace.steps[-1].probe
        condition = operator.name
        setup = [step.probe for step in trace.steps[:-1]]
        values = EvaluationContext(
            actor={"id": intervention.actor, "authenticated": intervention.actor != context.anonymous_actor},
            resource={"owner_id": context.owner_id}, state=dict(context.state), history=dict(context.history),
        ).as_dict()
        if operator.name == "repeat":
            values["history"][hypothesis.target_operation or hypothesis.action] = True
        return CounterfactualExperiment(hypothesis.id, hypothesis.family, baseline, intervention, condition, setup, list(context.observation_probes), values)
