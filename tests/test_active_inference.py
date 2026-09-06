import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Observation, Probe
from evidence import Evidence, EvidenceStore, context_from_evidence
from experiments.active_loop import ActivePolicyEngine
from experiments.generator import generate_counterfactuals
from experiments.selector import select
from experiments.selector import utility
from experiments.models import ExperimentCandidate
from inference.evidence_inducer import induce_policy_hypotheses
from inference.inducer import update_from_evidence
from inference.hypothesis import PolicyHypothesis
from inference.predicate import FieldRef, Predicate
from oracle import classify_effect, diff_snapshots
from planner import compile_counterfactual
from schema.models import Operation
from semantic import infer_semantics
from violation.counterfactual import CounterfactualContext


def test_evidence_induction_keeps_competing_hypotheses_and_updates_support():
    model = infer_semantics([Operation("POST", "/orders/{id}/refund", "refund")])
    evidence = Evidence(
        id="e1", operation_id="POST /orders/{id}/refund", resource_type="order", resource_id="1", actor_id="user_a",
        actor_relation="owner", resource_owner_id=None, pre_state={"status": "PAID"}, post_state={"status": "REFUNDED"},
        outcome="SUCCESS", status_code=200,
    )
    assert context_from_evidence(evidence).resource["owner_id"] == "user_a"
    hypotheses = induce_policy_hypotheses(model, [evidence])
    assert len(hypotheses) >= 3
    assert any(item.support_evidence for item in hypotheses)
    assert any(item.family == "ownership" for item in hypotheses)


def test_counterfactual_changes_only_actor_and_selector_uses_disagreement():
    hypotheses = induce_policy_hypotheses(infer_semantics([Operation("POST", "/orders/{id}/refund", "refund")]), [])
    baseline = Probe("refund", "user_a", "POST", "/orders/1/refund")
    candidates = generate_counterfactuals(hypotheses, baseline, CounterfactualContext(owner_id="user_a", alternate_actor="user_b", state={"status": "PAID"}))
    selected = select(candidates, len(hypotheses))
    assert selected.counterfactual.intervention.path == baseline.path
    assert selected.counterfactual.intervention.actor in {"user_a", "user_b"}
    assert selected.predictions


def test_differential_effect_prioritizes_protected_state_over_http_status():
    response = Observation(500, {}, {}, "user_b", "POST", "/orders/1/refund")
    effect = classify_effect({"status": "PAID"}, response, {"status": "REFUNDED"}, {"status"})
    assert effect.protected_effect
    assert effect.changed_fields == {"status": ("PAID", "REFUNDED")}
    assert diff_snapshots({"balance": 1}, {"balance": 2}) == {"balance": (1, 2)}
    metadata_only = classify_effect({"status": "PAID", "updatedAt": 1}, response, {"status": "PAID", "updatedAt": 2}, {"status"})
    assert not metadata_only.protected_effect
    assert metadata_only.classification == "ERROR"


def test_active_engine_updates_belief_from_execution_evidence():
    hypotheses = induce_policy_hypotheses(infer_semantics([Operation("POST", "/orders/{id}/refund", "refund")]), [])
    state = {"status": "PAID"}

    def execute(probe):
        state["status"] = "REFUNDED"
        return Observation(200, {}, {}, probe.actor, probe.method, probe.path, features={"operation_id": "POST /orders/{id}/refund"})

    engine = ActivePolicyEngine(hypotheses, EvidenceStore())
    outcomes = engine.run(Probe("refund", "user_a", "POST", "/orders/1/refund"), CounterfactualContext(owner_id="user_a", alternate_actor="user_b", state={"status": "PAID"}), 1, execute, lambda: dict(state), protected_fields={"status"})
    assert outcomes[0].result == "COUNTEREXAMPLE"
    assert engine.evidence.all()


def test_active_engine_does_not_repeat_a_counterfactual_with_larger_budget():
    hypotheses = induce_policy_hypotheses(infer_semantics([Operation("POST", "/orders/{id}/refund", "refund")]), [])
    state = {"status": "PAID"}
    executions = []

    def execute(probe):
        executions.append(probe.id)
        state["status"] = "REFUNDED"
        return Observation(200, {}, {}, probe.actor, probe.method, probe.path, features={"operation_id": "POST /orders/{id}/refund"})

    engine = ActivePolicyEngine(hypotheses)
    outcomes = engine.run(Probe("refund", "user_a", "POST", "/orders/1/refund"), CounterfactualContext(owner_id="user_a", alternate_actor="user_b", state={"status": "PAID"}), 10, execute, lambda: dict(state), protected_fields={"status"})
    assert len(outcomes) == len({outcome.candidate_id for outcome in outcomes})
    assert len(outcomes) < 10


def test_replay_and_state_counterfactuals_require_real_setup_context():
    hypotheses = induce_policy_hypotheses(infer_semantics([Operation("POST", "/orders/{id}/refund", "refund")]), [])
    baseline = Probe("refund", "user_a", "POST", "/orders/1/refund")
    setup = Probe("create", "user_a", "POST", "/orders")
    candidates = generate_counterfactuals(hypotheses, baseline, CounterfactualContext(
        owner_id="user_a", alternate_actor="user_b", state={"status": "CREATED"}, state_setup_probes=[setup],
    ))
    replay = next(item.counterfactual for item in candidates if item.counterfactual.family == "replay")
    state = next(item.counterfactual for item in candidates if item.counterfactual.family == "state-transition")
    assert replay.setup_probes == [baseline]
    assert state.setup_probes == [setup]
    hypothesis = next(item for item in hypotheses if item.id == replay.hypothesis_id)
    plan = compile_counterfactual(replay, hypothesis)
    assert plan.setup_steps[0].probe == baseline
    assert plan.intervention_step.probe == replay.intervention


def test_error_evidence_does_not_change_policy_support_or_contradiction():
    hypothesis = PolicyHypothesis("h", "authenticated", "POST /orders/{id}/refund", "order", target_operation="POST /orders/{id}/refund",
                                  predicates=[Predicate(FieldRef("actor", "authenticated"), "eq", True)])
    error = Evidence("error", "POST /orders/{id}/refund", "order", "1", "user_a", "owner", "user_a", {}, {}, "ERROR", 500)
    update_from_evidence([hypothesis], [error])
    assert not hypothesis.support_evidence
    assert not hypothesis.contradicting_evidence


def test_state_prediction_uses_snapshot_after_setup_not_declared_context_state():
    hypothesis = PolicyHypothesis("state", "state.status == CANCELLED", "POST /orders/{id}/refund", "order", family="state-transition",
                                  target_operation="POST /orders/{id}/refund", predicates=[Predicate(FieldRef("state", "status"), "eq", "CANCELLED")])
    state = {"status": "PAID"}

    def execute(probe):
        state["status"] = "CANCELLED" if probe.id == "setup" else "REFUNDED"
        return Observation(200, {}, {}, probe.actor, probe.method, probe.path, features={"operation_id": "POST /orders/{id}/refund"})

    outcome = ActivePolicyEngine([hypothesis]).run(
        Probe("refund", "user_a", "POST", "/orders/1/refund"),
        CounterfactualContext(state={"status": "PAID"}, state_setup_probes=[Probe("setup", "user_a", "POST", "/orders/1/cancel")]),
        1, execute, lambda: dict(state), protected_fields={"status"},
    )[0]
    assert outcome.result == "POLICY_HOLDS"


def test_utility_and_fingerprint_are_local_to_operation_and_context():
    hypotheses = induce_policy_hypotheses(infer_semantics([Operation("POST", "/orders/{id}/refund", "refund")]), [])
    baseline = Probe("refund", "user_a", "POST", "/orders/1/refund")
    first = generate_counterfactuals(hypotheses, baseline, CounterfactualContext(owner_id="user_a", alternate_actor="user_b", state={"status": "CREATED"}))[0]
    second = generate_counterfactuals(hypotheses, baseline, CounterfactualContext(owner_id="user_a", alternate_actor="user_b", state={"status": "PAID"}))[0]
    assert first.fingerprint != second.fingerprint
    assert utility(first, 100) == utility(first, 1)


def test_effect_oracle_accepts_adapter_selected_protected_fields():
    response = Observation(200, {}, {}, "user_b", "POST", "/transfer")
    effect = classify_effect({"balance": 10}, response, {"balance": 20}, {"balance"})
    assert effect.protected_effect
