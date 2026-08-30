import json
from dataclasses import asdict
from pathlib import Path

from actors import Actor, ActorManager
from core.models import Probe
from execution.trace_store import Trace, TraceStore
from inference import infer_ownership_policies, rank
from oracle import classify_effect, compare
from resources import ResourceTracker
from reports import write_finding
from targets.toy_policy import ToyPolicyTarget
from violation import violate_ownership


def run() -> dict:
    target = ToyPolicyTarget()
    actors = ActorManager([Actor("user_a", "USER"), Actor("user_b", "USER"), Actor("admin", "ADMIN")])
    trace = Trace()
    tracker = ResourceTracker()

    def execute(probe):
        observation = target.execute(probe)
        trace.append(observation)
        tracker.observe(observation)
        return observation

    created = execute(Probe("create_order", "user_a", "POST", "/orders"))
    order_id = created.extracted_ids["resource_id"]
    execute(Probe("pay_order", "user_a", "POST", f"/orders/{order_id}/pay"))
    valid_refund = Probe("refund_order", "user_a", "POST", f"/orders/{order_id}/refund")

    # Fresh paid order is needed because the valid evidence call should not consume the counterexample target.
    evidence_order = execute(Probe("create_evidence_order", "user_a", "POST", "/orders"))
    evidence_id = evidence_order.extracted_ids["resource_id"]
    execute(Probe("pay_evidence_order", "user_a", "POST", f"/orders/{evidence_id}/pay"))
    valid = execute(Probe("refund_evidence_order", "user_a", "POST", f"/orders/{evidence_id}/refund"))

    store = TraceStore()
    store.add(trace)
    hypotheses = rank(infer_ownership_policies(store, tracker))
    refund_hypothesis = next(hypothesis for hypothesis in hypotheses if hypothesis.action.endswith("/refund"))
    resource = tracker.get("order", order_id)
    counterexample = violate_ownership(refund_hypothesis, valid_refund, resource, actors)
    before = dict(target.orders[order_id])
    observed = execute(counterexample.probe)
    after = dict(target.orders[order_id])
    effect = classify_effect(before, observed, after)
    result = compare(counterexample.expected, effect)
    return {
        "hypothesis": asdict(refund_hypothesis), "counterexample": asdict(counterexample),
        "expected": counterexample.expected, "observed_status": observed.status_code,
        "before": before, "after": after, "effect": asdict(effect), "result": result,
    }


if __name__ == "__main__":
    result = run()
    output = Path(__file__).resolve().parents[1] / "output" / "policy-toy-result.json"
    write_finding(output, result)
    print(json.dumps(result, indent=2))
