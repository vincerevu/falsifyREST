import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evidence import Evidence
from experiments.policy_guided_loop import prepare_experiments
from inference.candidate_generator import POLICY_FAMILIES, generate_candidates
from schema.models import Operation
from semantic import infer_semantics
from semantic.llm_semantic import DisabledSemanticEnricher, OpenAICompatibleSemanticEnricher


def settle_operation():
    return Operation("POST", "/claims/{claimId}/settle", "settle")


def settle_evidence():
    return Evidence("e1", "settle", "claim", "12", "user_a", "owner", "user_a", {"status": "PENDING"}, {"status": "SETTLED"}, "SUCCESS", 200)


def test_parser_exports_static_facts_without_policy_family_rules():
    semantic = infer_semantics([settle_operation()]).operations[0]
    assert semantic.resource == "claim"
    assert semantic.action == "settle"
    assert semantic.static_facts["has_path_identifier"]
    assert semantic.family_priors == {}
    assert semantic.prior_source == "uniform"


def test_generic_registry_instantiates_all_families_from_execution_evidence():
    model = infer_semantics([settle_operation()])
    hypotheses = generate_candidates(model, [settle_evidence()])
    assert {"ownership", "authorization", "state-transition", "replay"}.issubset({item.family for item in hypotheses})
    assert {family.name for family in POLICY_FAMILIES} == {"ownership", "authorization", "state-transition", "replay"}


def test_llm_only_adjusts_optional_family_priors():
    operation = infer_semantics([settle_operation()]).operations[0]
    assert DisabledSemanticEnricher().enrich(operation) is operation
    enriched = OpenAICompatibleSemanticEnricher._apply(operation, {
        "resource": "claim", "action": "settle", "possible_state_fields": ["status"],
        "family_priors": {"ownership": 0.6, "state-transition": 0.9, "ignored": 1.0},
    })
    assert enriched.family_priors == {"ownership": 0.6, "state-transition": 0.9}
    assert enriched.prior_source == "llm"
    assert "status" in enriched.state_fields


def test_prepare_experiments_runs_llm_off_with_uniform_prior_and_evidence(monkeypatch):
    monkeypatch.setenv("FALSIFYREST_LLM_PROVIDER", "disabled")
    result = prepare_experiments([settle_operation()], evidence=[settle_evidence()])
    assert result["semantic_prior_source"] == ["uniform"]
    assert len(result["hypotheses"]) >= 4
    assert result["semantic_operations"][0]["static_facts"]["method"] == "POST"
