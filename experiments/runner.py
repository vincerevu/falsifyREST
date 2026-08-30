import argparse
import json
import random
import shutil
from pathlib import Path

from core.belief import normalize, update_belief
from core.models import Hypothesis, Probe
from core.oracle import security_oracle
from core.prediction import predict
from core.selector import ProbeSelector
from targets.toy_order import ToyOrderTarget


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROBES = [
    Probe("get_order", "owner", "GET", "/order/1", cost=0.5),
    Probe("submit_order", "owner", "POST", "/order/1/submit", risk=0.1),
    Probe("approve_order", "manager", "POST", "/order/1/approve", risk=0.2),
]


def initial_belief() -> list[Hypothesis]:
    return [
        Hypothesis("H1", "draft", {"get_order": True, "submit_order": True, "approve_order": False}, {"order": "owner"}, weight=0.4),
        Hypothesis("H2", "submitted", {"get_order": True, "submit_order": False, "approve_order": True}, {"order": "owner"}, weight=0.5),
        Hypothesis("H3", "approved", {"get_order": True, "submit_order": False, "approve_order": False}, {"order": "owner"}, weight=0.1),
    ]


def select_facts_only(probes, _belief, _rng):
    return next((p for p in probes if p.id == "get_order"), probes[0]), {p.id: 0.0 for p in probes}


def select_belief_heuristic(probes, _belief, rng):
    selected = rng.choice(probes)
    return selected, {p.id: 0.0 for p in probes}


def select_secbelief(probes, belief, _rng):
    return ProbeSelector().select(probes, belief, predict)


def run_once(mode: str, seed: int, budget: int, trace_path: Path | None = None) -> dict:
    rng = random.Random(seed)
    target = ToyOrderTarget()
    belief = initial_belief()
    probes = list(DEFAULT_PROBES)
    history = []
    verdict = "blind"
    first_violation = None
    resolved_at = None
    selector = {"facts_only": select_facts_only, "belief_heuristic": select_belief_heuristic, "secbelief": select_secbelief}[mode]
    if trace_path:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_file = trace_path.open("w", encoding="utf-8")
    else:
        trace_file = None
    try:
        for step in range(budget):
            available = [p for p in probes if p.id not in {item["probe"] for item in history}]
            if not available:
                break
            selected, scores = selector(available, belief, rng)
            belief_before = {h.id: round(h.weight, 6) for h in belief}
            observation = target.execute(selected)
            if selected.id == "approve_order":
                verdict = security_oracle(belief, selected, observation)
                if verdict == "violation" and first_violation is None:
                    first_violation = step + 1
            update_belief(belief, selected, observation, predict)
            if max(h.weight for h in belief) >= 0.8 and resolved_at is None:
                resolved_at = step + 1
            event = {
                "run": seed, "step": step + 1, "mode": mode, "belief_before": belief_before,
                "candidate_probes": [p.id for p in available], "selected": selected.id,
                "scores": {k: round(v, 6) for k, v in scores.items()},
                "observed_status": observation.status,
                "observed_features": observation.features,
                "belief_after": {h.id: round(h.weight, 6) for h in belief},
                "verdict": verdict,
            }
            history.append({"probe": selected.id, "status": observation.status})
            if trace_file:
                trace_file.write(json.dumps(event) + "\n")
            if verdict == "violation":
                break
    finally:
        if trace_file:
            trace_file.close()
    return {"mode": mode, "seed": seed, "verdict": verdict, "requests": len(history), "resolved_at": resolved_at, "first_violation": first_violation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--budget", type=int, default=5)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    traces = out / "traces"
    if traces.exists():
        shutil.rmtree(traces)
    modes = ["facts_only", "belief_heuristic", "secbelief"]
    results = []
    for mode in modes:
        for index in range(args.runs):
            results.append(run_once(mode, args.seed + index, args.budget, traces / f"{mode.replace(' ', '_')}.jsonl" if index == 0 else None))
    summary = {}
    for mode in modes:
        rows = [r for r in results if r["mode"] == mode]
        summary[mode] = {
            "runs": len(rows),
            "violations": sum(r["verdict"] == "violation" for r in rows),
            "benign": sum(r["verdict"] == "benign" for r in rows),
            "blind": sum(r["verdict"] == "blind" for r in rows),
            "avg_requests": round(sum(r["requests"] for r in rows) / len(rows), 3),
            "avg_requests_to_first_violation": round(sum(r["first_violation"] or args.budget for r in rows) / len(rows), 3),
        }
    (out / "summary.json").write_text(json.dumps({"config": vars(args), "summary": summary, "runs": results}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
