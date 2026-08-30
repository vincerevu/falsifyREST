import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.policy_runner import run
from schema import parse_operations


def test_openapi_parser_extracts_operations():
    operations = parse_operations({"paths": {"/orders/{id}/refund": {"post": {"operationId": "refund", "responses": {"200": {"description": "ok"}}}}}})
    assert operations[0].operation_id == "refund"
    assert operations[0].method == "POST"


def test_policy_flow_finds_effective_cross_user_counterexample():
    result = run()
    assert result["hypothesis"]["subject_relation"] == "actor == resource.owner"
    assert result["hypothesis"]["action"] == "POST /orders/{id}/refund"
    assert result["counterexample"]["actor"] == "user_b"
    assert result["effect"]["classification"] == "EFFECTIVE_SUCCESS"
    assert result["result"] == "COUNTEREXAMPLE"
