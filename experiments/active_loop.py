"""Orchestration for hypothesis-guided counterexample search."""
from collections.abc import Callable
from dataclasses import replace

from core.models import ExecutionTrace, Observation, Probe, TraceStep
from evidence import EvidenceStore, extract_evidence
from inference.inducer import update_from_evidence
from inference.hypothesis import PolicyHypothesis
from oracle import EffectResult, FalsificationOracle, classify_effect, compare_prediction
from planner import compile_trace
from resources.tracker import ResourceTracker
from search import CounterexampleSearchEngine, SeedSelector
from search.operators import ActorSwap, OmitStep, Repeat, Reorder, ResourceSwap
from violation.counterfactual import CounterfactualContext

from .models import ExperimentOutcome


class ActivePolicyEngine:
    """Ranks hypotheses, selects real workflow seeds, and delegates mutation to search."""
    def __init__(self, hypotheses: list[PolicyHypothesis], evidence: EvidenceStore | None = None,
                 tracker: ResourceTracker | None = None, search: CounterexampleSearchEngine | None = None):
        self.hypotheses = hypotheses
        self.evidence = evidence or EvidenceStore()
        self.tracker = tracker
        self.attempted: set[str] = set()
        self.seed_selector = SeedSelector()
        self.search = search or CounterexampleSearchEngine([ActorSwap(), ResourceSwap(), Repeat(), OmitStep(), Reorder()])
        self.oracle = FalsificationOracle()

    def run(self, baseline: Probe | ExecutionTrace | list[ExecutionTrace], context: CounterfactualContext, budget: int,
            execute: Callable[[Probe], Observation], snapshot: Callable[[], dict], resource_type: str = "resource",
            protected_fields: set[str] | None = None) -> list[ExperimentOutcome]:
        seeds = list(baseline) if isinstance(baseline, list) else [baseline if isinstance(baseline, ExecutionTrace) else ExecutionTrace.from_probe(baseline)]
        if context.state_setup_probes:
            seeds = [ExecutionTrace(seed.id, [*(TraceStep(probe) for probe in context.state_setup_probes), *seed.steps]) for seed in seeds]
        outcomes: list[ExperimentOutcome] = []
        outcome_index: dict[str, int] = {}
        remaining = budget
        for hypothesis in sorted(self.hypotheses, key=lambda item: item.confidence, reverse=True):
            if remaining <= 0:
                break
            for selected_seed in self.seed_selector.select(hypothesis, seeds):
                if remaining <= 0:
                    break

                def evaluate(node) -> bool:
                    plan = compile_trace(node.trace, hypothesis)
                    for step in plan.setup_steps:
                        if step.probe is not None:
                            execute(step.probe)
                    before = snapshot()
                    if plan.intervention_step is None or plan.intervention_step.probe is None:
                        raise RuntimeError("compiled trace has no executable target")
                    observed = execute(plan.intervention_step.probe)
                    after = snapshot()
                    if observed.features.get("protected_disclosure"):
                        effect = EffectResult("EFFECTIVE_DISCLOSURE", True, "target adapter observed protected resource data")
                    else:
                        effect = classify_effect(before, observed, after, hypothesis.protected_fields or protected_fields)
                    actual_context = {
                        "actor": {"id": observed.actor, "authenticated": observed.actor != context.anonymous_actor},
                        "resource": {"owner_id": context.owner_id}, "state": dict(before), "history": {},
                    }
                    if "repeat" in node.transformations:
                        actual_context["history"][hypothesis.target_operation or hypothesis.action] = True
                    prediction = hypothesis.predict(actual_context)
                    result = compare_prediction(prediction, effect)
                    observed_with_state = replace(observed, state_before=dict(before), state_after=dict(after))
                    evidence = extract_evidence(observed_with_state, self.tracker, source_trace=node.id,
                                                evaluation_context=actual_context)
                    self.evidence.add(evidence)
                    update_from_evidence(self.hypotheses, self.evidence.all())
                    control_observation = node.seed_trace.steps[-1].observation
                    control_effect = None
                    if control_observation is not None:
                        control_effect = classify_effect(
                            control_observation.state_before, control_observation,
                            control_observation.state_after, hypothesis.protected_fields or protected_fields,
                        )
                    verdict = self.oracle.evaluate(
                        hypothesis, node.seed_trace, node.trace, effect, actual_context,
                        control_effect, observed.status_code,
                    )
                    falsified = verdict.falsified and result == "COUNTEREXAMPLE"
                    outcome = ExperimentOutcome(hypothesis.id, "ALLOW" if effect.protected_effect else "DENY", result,
                                                evidence.id, verdict.classification, verdict.witness)
                    # The public outcome list reports the latest witness per
                    # hypothesis; detailed attempts remain in evidence/search.
                    if hypothesis.id in outcome_index:
                        outcomes[outcome_index[hypothesis.id]] = outcome
                    else:
                        outcome_index[hypothesis.id] = len(outcomes)
                        outcomes.append(outcome)
                    self.attempted.add(node.id)
                    return falsified

                result = self.search.search(hypothesis, selected_seed, remaining, context, evaluate)
                remaining -= len(result.evaluated)
                if result.counterexample:
                    break
        return outcomes
