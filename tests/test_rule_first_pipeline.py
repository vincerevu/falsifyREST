import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Observation
from experiments.policy_guided_loop import prepare_experiments
from feedback import FeedbackStore, apply_result
from inference.rule_generator import generate_rule_hypotheses
from planner import plan_experiments
from schema.models import Operation
from semantic import infer_semantics
from semantic.llm_semantic import DisabledSemanticEnricher, OpenAICompatibleSemanticEnricher
from state import StateModel


def operations():
    return [
        Operation("POST", "/orders/{orderId}/refund", "refund"),
        Operation("POST", "/orders/{orderId}/pay", "pay"),
        Operation("GET", "/orders/{orderId}", "getOrder"),
    ]


def test_rule_semantics_cover_ownership_state_and_replay_without_llm():
    model = infer_semantics(operations())
    hypotheses = generate_rule_hypotheses(model)
    assert {"ownership", "state-transition", "replay"}.issubset({item.family for item in hypotheses})
    assert all(item.target_operation for item in hypotheses)
    assert all(item.confidence == 0.5 for item in hypotheses)


def test_semantic_enrichment_is_bounded_metadata_only():
    original = infer_semantics(operations()).operations[0]
    assert DisabledSemanticEnricher().enrich(original) is original
    enriched = OpenAICompatibleSemanticEnricher._apply(original, {
        "resource": "invoice", "action": "refund", "security_concepts": ["ownership", "ignored"],
        "likely_invariants": ["only creator may refund"],
    })
    assert enriched.resource == "invoice"
    assert "ignored" not in enriched.security_concepts
    assert enriched.source == "rule+llm"


def test_planner_builds_distinct_reproducible_sequences_and_feedback_updates_only_after_oracle():
    hypotheses = generate_rule_hypotheses(infer_semantics(operations()))
    planned = plan_experiments(hypotheses)
    ownership = next(item for item in planned if item.family == "ownership")
    replay = next(item for item in planned if item.family == "replay")
    assert [step.actor for step in ownership.steps] == ["actor_a", "actor_b", "observer"]
    assert "replay identical action" == replay.steps[1].purpose
    store = FeedbackStore()
    hypothesis = next(item for item in hypotheses if item.family == "ownership")
    apply_result(store, hypothesis, "COUNTEREXAMPLE")
    assert hypothesis.status == "CONFIRMED"
    assert not store.unexplored(hypothesis)


def test_state_model_learns_only_observed_transition():
    observation = Observation(200, {}, {}, "actor_a", "POST", "pay", extracted_ids={"order": "12"}, state_before={"status": "CREATED"}, state_after={"status": "PAID"})
    state = StateModel()
    transitions = state.observe(observation, "order")
    assert transitions[0].pre_state == "CREATED"
    assert transitions[0].post_state == "PAID"


def test_policy_guided_loop_defaults_to_rule_only(monkeypatch):
    monkeypatch.delenv("FALSIFYREST_LLM_PROVIDER", raising=False)
    result = prepare_experiments(operations())
    assert result["semantic_source"] == ["rule"]
    assert len(result["experiments"]) >= 3
