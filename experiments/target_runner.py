"""Adapter-driven active execution shared by all REST targets."""
from __future__ import annotations

import re
from dataclasses import asdict

from adapters.target import TargetAdapter
from core.models import Probe
from experiments.active_loop import ActivePolicyEngine
from inference.hypothesis import PolicyHypothesis


def operation_matches(target_operation: str | None, probe: Probe) -> bool:
    """Match an OpenAPI operation template to a concrete probe without domain rules."""
    if not target_operation:
        return False
    method, template = target_operation.split(" ", 1)
    if method.upper() != probe.method.upper():
        return False
    pattern = re.sub(r"\{[^}]+\}", r"[^/]+", template.rstrip("/"))
    return re.fullmatch(pattern, probe.path.rstrip("/")) is not None


def relevant_hypotheses(hypotheses: list[PolicyHypothesis], baseline: Probe) -> list[PolicyHypothesis]:
    return [item for item in hypotheses if operation_matches(item.target_operation, baseline)]


def run_with_adapter(
    hypotheses: list[PolicyHypothesis],
    baselines: list[Probe],
    adapter: TargetAdapter,
    budget_per_seed: int,
) -> list[dict]:
    """Run the generic counterexample engine through a target-specific boundary.

    Authentication, resource/state setup, snapshots, resets, and protected-field
    declarations are adapter responsibilities. The search/inference/oracle layers
    remain target-agnostic.
    """
    results: list[dict] = []
    for baseline in baselines:
        relevant = relevant_hypotheses(hypotheses, baseline)
        if not relevant:
            continue
        adapter.reset()
        context = adapter.context_for(baseline)
        engine = ActivePolicyEngine(relevant)
        outcomes = engine.run(
            baseline,
            context,
            budget_per_seed,
            adapter.execute,
            adapter.snapshot,
            protected_fields=adapter.protected_fields_for(baseline),
        )
        results.append({
            "baseline": asdict(baseline),
            "outcomes": [asdict(item) for item in outcomes],
        })
    return results
