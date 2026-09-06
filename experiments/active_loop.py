"""Active black-box policy inference loop. Target-specific auth/setup remains an adapter concern."""
from collections.abc import Callable
from dataclasses import replace

from core.models import Observation, Probe
from evidence import EvidenceStore, extract_evidence
from inference.inducer import update_from_evidence
from inference.hypothesis import PolicyHypothesis
from oracle import classify_effect, compare_prediction
from planner import compile_counterfactual
from resources.tracker import ResourceTracker
from violation.counterfactual import CounterfactualContext

from .generator import generate_counterfactuals
from .models import ExperimentOutcome
from .selector import select


class ActivePolicyEngine:
    def __init__(self, hypotheses: list[PolicyHypothesis], evidence: EvidenceStore | None = None, tracker: ResourceTracker | None = None):
        self.hypotheses = hypotheses
        self.evidence = evidence or EvidenceStore()
        self.tracker = tracker

    def run(self, baseline: Probe, context: CounterfactualContext, budget: int,
            execute: Callable[[Probe], Observation], snapshot: Callable[[], dict], resource_type: str = "resource") -> list[ExperimentOutcome]:
        outcomes: list[ExperimentOutcome] = []
        for _ in range(budget):
            candidates = generate_counterfactuals(self.hypotheses, baseline, context)
            if not candidates:
                break
            candidate = select(candidates, len(self.hypotheses))
            hypothesis = next(item for item in self.hypotheses if item.id == candidate.id)
            plan = compile_counterfactual(candidate.counterfactual, hypothesis)
            for step in plan.setup_steps:
                if step.probe is not None:
                    execute(step.probe)
            before = snapshot()
            if plan.intervention_step is None or plan.intervention_step.probe is None:
                raise RuntimeError("compiled plan has no executable intervention")
            observed = execute(plan.intervention_step.probe)
            for step in plan.observation_steps:
                if step.probe is not None:
                    execute(step.probe)
            after = snapshot()
            effect = classify_effect(before, observed, after)
            prediction = candidate.predictions.get(hypothesis.id, "DENY")
            result = compare_prediction(prediction, effect)
            observed = replace(observed, state_before=dict(before), state_after=dict(after))
            evidence = extract_evidence(observed, self.tracker, source_trace="active")
            self.evidence.add(evidence)
            update_from_evidence(self.hypotheses, self.evidence.all())
            outcomes.append(ExperimentOutcome(candidate.id, "ALLOW" if effect.protected_effect else "DENY", result, evidence.id))
        return outcomes
