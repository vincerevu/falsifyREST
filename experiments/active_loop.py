"""Active black-box policy inference loop. Target-specific auth/setup remains an adapter concern."""
from collections.abc import Callable

from core.models import Observation, Probe
from evidence import EvidenceStore, extract_evidence
from inference.inducer import update_from_evidence
from inference.hypothesis import PolicyHypothesis
from oracle import classify_effect, compare
from planner import compile_counterfactual

from .generator import generate_counterfactuals
from .models import ExperimentOutcome
from .selector import select


class ActivePolicyEngine:
    def __init__(self, hypotheses: list[PolicyHypothesis], evidence: EvidenceStore | None = None):
        self.hypotheses = hypotheses
        self.evidence = evidence or EvidenceStore()

    def run(self, baseline: Probe, alternate_actor: str | None, budget: int,
            execute: Callable[[Probe], Observation], snapshot: Callable[[], dict], resource_type: str = "resource") -> list[ExperimentOutcome]:
        outcomes: list[ExperimentOutcome] = []
        for _ in range(budget):
            candidates = generate_counterfactuals(self.hypotheses, baseline, alternate_actor)
            if not candidates:
                break
            candidate = select(candidates, len(self.hypotheses))
            _plan = compile_counterfactual(candidate.counterfactual, next(item for item in self.hypotheses if item.id == candidate.id))
            before = snapshot()
            observed = execute(candidate.counterfactual.intervention)
            after = snapshot()
            effect = classify_effect(before, observed, after)
            result = compare("DENY", effect)
            evidence = extract_evidence(observed, source_trace="active")
            self.evidence.add(evidence)
            update_from_evidence(self.hypotheses, self.evidence.all())
            outcomes.append(ExperimentOutcome(candidate.id, "ALLOW" if effect.protected_effect else "DENY", result, evidence.id))
        return outcomes
