"""Full-spec Juice Shop benchmark integration.

The CLI imports a captured EvoMaster/proxy trace and produces an evidence-driven
candidate inventory for every OpenAPI operation. Live counterfactual execution is
exposed as an injected adapter API: target-specific authentication, resource setup,
and snapshots must be supplied explicitly instead of being guessed from OpenAPI.
"""
import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from adapters.proxy import ProxyTraceImporter
from core.models import Observation, Probe
from evidence import EvidenceStore, extract_evidence
from execution.trace_store import TraceStore
from experiments.active_loop import ActivePolicyEngine
from inference.evidence_inducer import induce_policy_hypotheses
from inference.hypothesis import PolicyHypothesis
from resources import ResourceTracker
from schema import parse_operations
from schema.models import Operation
from semantic import enricher_from_env, infer_semantics
from violation.counterfactual import CounterfactualContext


@dataclass
class BenchmarkAnalysis:
    operation_count: int
    traced_operation_count: int
    observation_count: int
    evidence_count: int
    hypothesis_counts: dict[str, int]
    uncovered_operations: list[str]


def _path_match(template: str, path: str) -> dict[str, str] | None:
    pattern = re.sub(r"\{([^}]+)\}", r"(?P<\1>[^/]+)", template.rstrip("/"))
    match = re.fullmatch(pattern, path.rstrip("/"))
    return match.groupdict() if match else None


def normalize_traces(traces, operations: list[Operation], model) -> list[Observation]:
    """Attach OpenAPI operation/resource facts to proxy observations without policy rules."""
    by_signature = [(operation, next(item for item in model.operations if item.operation is operation)) for operation in operations]
    normalized = []
    for trace in traces:
        for observation in trace.observations:
            for operation, semantic in by_signature:
                if operation.method != observation.method:
                    continue
                parameters = _path_match(operation.path, observation.endpoint)
                if parameters is None:
                    continue
                observation.features = {**observation.features, "operation_id": operation.operation_id, "resource_type": semantic.resource}
                observation.extracted_ids = {**parameters, **observation.extracted_ids}
                normalized.append(observation)
                break
    return normalized


def analyze(config_path: str | Path, trace_path: str | Path) -> tuple[BenchmarkAnalysis, list[PolicyHypothesis], EvidenceStore]:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    operations = parse_operations(config["target"]["openapi"])
    model = infer_semantics(operations)
    enricher = enricher_from_env()
    model.operations = [enricher.enrich(operation) for operation in model.operations]
    traces = ProxyTraceImporter().load(trace_path)
    observations = normalize_traces(traces, operations, model)
    tracker, evidence = ResourceTracker(), EvidenceStore()
    for observation in observations:
        tracker.observe(observation)
        evidence.add(extract_evidence(observation, tracker, source_trace=str(trace_path)))
    hypotheses = induce_policy_hypotheses(model, evidence.all())
    traced = {item.features.get("operation_id") for item in observations}
    all_ids = {operation.operation_id for operation in operations}
    report = BenchmarkAnalysis(
        operation_count=len(operations), traced_operation_count=len(traced), observation_count=len(observations), evidence_count=len(evidence.all()),
        hypothesis_counts=dict(Counter(item.family for item in hypotheses)), uncovered_operations=sorted(all_ids - traced),
    )
    return report, hypotheses, evidence


def run_active(hypotheses: list[PolicyHypothesis], seeds: list[tuple[Probe, CounterfactualContext]],
               execute: Callable[[Probe], Observation], snapshot: Callable[[], dict], budget_per_seed: int,
               protected_fields: set[str]) -> list[dict]:
    """Execute adapter-supplied concrete counterfactual contexts using the generic core engine."""
    results = []
    for baseline, context in seeds:
        relevant = []
        for item in hypotheses:
            if not item.target_operation:
                continue
            method, template = item.target_operation.split(" ", 1)
            if method == baseline.method and _path_match(template, baseline.path) is not None:
                relevant.append(item)
        if not relevant:
            continue
        engine = ActivePolicyEngine(relevant)
        outcomes = engine.run(baseline, context, budget_per_seed, execute, snapshot, protected_fields=protected_fields)
        results.append({"baseline": asdict(baseline), "outcomes": [asdict(item) for item in outcomes]})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze full Juice Shop OpenAPI coverage from a normalized proxy JSONL trace.")
    parser.add_argument("--config", default="configs/juiceshop.local.json", help="Ignored local config; copy the example first.")
    parser.add_argument("--trace", required=True, help="Normalized proxy JSONL captured during EvoMaster exploration.")
    parser.add_argument("--output", default="output/juiceshop-benchmark-analysis.json")
    args = parser.parse_args()
    report, hypotheses, _ = analyze(args.config, args.trace)
    payload = {"analysis": asdict(report), "hypotheses": [asdict(item) for item in hypotheses],
               "note": "Analysis is trace-derived. Use run_active() with explicit target auth/setup/snapshot adapters for live counterfactual execution."}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    main()
