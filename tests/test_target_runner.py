from core.models import Probe
from experiments.target_runner import operation_matches, relevant_hypotheses
from inference.hypothesis import PolicyHypothesis


def test_operation_matches_openapi_template_without_domain_rules():
    probe = Probe("p", "actor-a", "PATCH", "/widgets/42/activate")
    assert operation_matches("PATCH /widgets/{widget_id}/activate", probe)
    assert not operation_matches("POST /widgets/{widget_id}/activate", probe)
    assert not operation_matches("PATCH /accounts/{account_id}/activate", probe)


def test_relevant_hypotheses_are_selected_by_method_and_template_only():
    baseline = Probe("p", "actor-a", "DELETE", "/documents/abc")
    hypotheses = [
        PolicyHypothesis("matching", "actor.authenticated", "DELETE /documents/{id}", "document", target_operation="DELETE /documents/{id}"),
        PolicyHypothesis("other-method", "actor.authenticated", "GET /documents/{id}", "document", target_operation="GET /documents/{id}"),
        PolicyHypothesis("other-resource", "actor.authenticated", "DELETE /folders/{id}", "folder", target_operation="DELETE /folders/{id}"),
    ]

    assert [item.id for item in relevant_hypotheses(hypotheses, baseline)] == ["matching"]
