import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Observation, Probe
from evidence import Evidence, EvidenceStore
from experiments.active_loop import ActivePolicyEngine
from experiments.generator import generate_counterfactuals
from experiments.selector import select
from inference.evidence_inducer import induce_policy_hypotheses
from oracle import classify_effect, diff_snapshots
from schema.models import Operation
from semantic import infer_semantics


def test_evidence_induction_keeps_competing_hypotheses_and_updates_support():
    model = infer_semantics([Operation("POST", "/orders/{id}/refund", "refund")])
    evidence = Evidence("e1", "POST /orders/{id}/refund", "order", "1", "user_a", "owner", {"status": "PAID"}, {"status": "REFUNDED"}, "SUCCESS", 200,
                        response_features={"owner": "user_a"})
    hypotheses = induce_policy_hypotheses(model, [evidence])
    assert len(hypotheses) >= 3
    assert any(item.support_evidence for item in hypotheses)
    assert any(item.family == "ownership" for item in hypotheses)


def test_counterfactual_changes_only_actor_and_selector_uses_disagreement():
    hypotheses = induce_policy_hypotheses(infer_semantics([Operation("POST", "/orders/{id}/refund", "refund")]), [])
    baseline = Probe("refund", "user_a", "POST", "/orders/1/refund")
    candidates = generate_counterfactuals(hypotheses, baseline, "user_b")
    selected = select(candidates, len(hypotheses))
    assert selected.counterfactual.intervention.path == baseline.path
    assert selected.counterfactual.intervention.actor in {"user_a", "user_b"}
    assert selected.predictions


def test_differential_effect_prioritizes_protected_state_over_http_status():
    response = Observation(500, {}, {}, "user_b", "POST", "/orders/1/refund")
    effect = classify_effect({"status": "PAID"}, response, {"status": "REFUNDED"})
    assert effect.protected_effect
    assert effect.changed_fields == {"status": ("PAID", "REFUNDED")}
    assert diff_snapshots({"balance": 1}, {"balance": 2}) == {"balance": (1, 2)}


def test_active_engine_updates_belief_from_execution_evidence():
    hypotheses = induce_policy_hypotheses(infer_semantics([Operation("POST", "/orders/{id}/refund", "refund")]), [])
    state = {"status": "PAID"}

    def execute(probe):
        state["status"] = "REFUNDED"
        return Observation(200, {}, {}, probe.actor, probe.method, probe.path, features={"operation_id": "POST /orders/{id}/refund"})

    engine = ActivePolicyEngine(hypotheses, EvidenceStore())
    outcomes = engine.run(Probe("refund", "user_a", "POST", "/orders/1/refund"), "user_b", 1, execute, lambda: dict(state))
    assert outcomes[0].result == "COUNTEREXAMPLE"
    assert engine.evidence.all()
