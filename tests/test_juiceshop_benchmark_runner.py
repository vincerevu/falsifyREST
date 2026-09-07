import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.juiceshop_benchmark_runner import analyze, write_csv
from experiments.juiceshop_benchmark_runner import run_active
from core.models import Observation, Probe
from violation.counterfactual import CounterfactualContext


def test_full_spec_analysis_imports_trace_into_generic_evidence_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("FALSIFYREST_LLM_PROVIDER", "disabled")
    spec = {"paths": {"/claims/{claimId}/settle": {"post": {"operationId": "settle", "parameters": [{"name": "claimId", "in": "path"}], "responses": {"200": {"description": "ok"}}}}}}
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"target": {"openapi": str(spec_path)}}), encoding="utf-8")
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(json.dumps({"status_code": 200, "method": "POST", "endpoint": "/claims/12/settle", "actor": "user_a",
                                      "state_before": {"status": "PENDING"}, "state_after": {"status": "SETTLED"},
                                      "features": {"owner": "user_a"}}) + "\n", encoding="utf-8")
    report, hypotheses, evidence = analyze(config_path, trace_path)
    assert report.operation_count == report.traced_operation_count == 1
    assert report.evidence_count == 1
    assert {item.family for item in hypotheses} == {"ownership", "authorization", "state-transition", "replay"}
    assert evidence.all()[0].operation_id == "settle"

    state = {"status": "PENDING"}

    def execute(probe):
        state["status"] = "SETTLED"
        return Observation(200, {}, {}, probe.actor, probe.method, probe.path, features={"operation_id": "settle"})

    active = run_active(hypotheses, [(Probe("settle", "user_a", "POST", "/claims/12/settle"),
                                      CounterfactualContext(owner_id="user_a", alternate_actor="user_b", state={"status": "PENDING"}))],
                        execute, lambda: dict(state), 1, {"status"})
    assert active and active[0]["outcomes"]
    csv_path = write_csv(tmp_path / "summary.csv", report)
    assert "traced_operation_count" in csv_path.read_text(encoding="utf-8")
