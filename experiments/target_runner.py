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


def run_with_adapter(hypotheses: list[PolicyHypothesis], baselines: list[Probe], adapter: TargetAdapter,
                     budget_per_seed: int, manage_lifecycle: bool = True,
                     seeds_prepared: bool = False) -> list[dict]:
    """Run the one generic active pipeline through target-owned mechanics."""
    results: list[dict] = []
    if manage_lifecycle:
        adapter.setup()
    try:
        for baseline in baselines:
            baseline = baseline if seeds_prepared else adapter.prepare_seed(baseline)
            if baseline is None:
                continue
            relevant = relevant_hypotheses(hypotheses, baseline)
            if not relevant:
                continue
            context = adapter.context_for(baseline)
            outcomes = ActivePolicyEngine(relevant).run(
                baseline, context, budget_per_seed, adapter.execute, adapter.snapshot,
                protected_fields=adapter.protected_fields_for(baseline),
                reset=adapter.reset if getattr(adapter, "supports_fresh_control", False) else None,
            )
            results.append({"baseline": asdict(baseline), "outcomes": [asdict(item) for item in outcomes]})
    finally:
        if manage_lifecycle:
            adapter.reset()
    return results
