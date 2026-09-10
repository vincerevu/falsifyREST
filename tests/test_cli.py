import json

from cli.app import app
from cli.runner import _seed_probes, run
from cli.session import ExplorationConfig, RunConfig, TargetConfig, load_config, save_config
from typer.testing import CliRunner


def _openapi(path):
    path.write_text(json.dumps({"paths": {"/claims/{claimId}": {"get": {"operationId": "getClaim", "responses": {"200": {"description": "ok"}}}}}}), encoding="utf-8")


def test_run_config_round_trips_as_profile_and_uses_generic_preflight(tmp_path):
    spec = tmp_path / "openapi.json"
    _openapi(spec)
    config = RunConfig(TargetConfig("http://localhost:3000", str(spec)), ExplorationConfig("skip"), budget=7, output_dir=str(tmp_path / "output"))
    profile = save_config(config, tmp_path / "profile.yaml")
    loaded = load_config(profile)
    result = run(loaded)
    assert loaded.budget == 7
    assert result.operation_count == 1
    assert (tmp_path / "output" / "run-report.md").is_file()


def test_noninteractive_cli_builds_the_same_run_config_shape(tmp_path, monkeypatch):
    spec = tmp_path / "openapi.json"
    _openapi(spec)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["run", "--no-interactive", "--target", "http://localhost:3000", "--openapi", str(spec), "--mode", "rule-only", "--budget", "3"])
    assert result.exit_code == 0, result.stdout
    assert "OpenAPI operations" in result.stdout
    assert "1" in result.stdout


def test_live_seed_extraction_uses_successful_requests_for_configured_actors(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text("\n".join([
        json.dumps({"status_code": 200, "method": "GET", "endpoint": "/basket/1", "actor": "owner", "request_body": {}}),
        json.dumps({"status_code": 403, "method": "GET", "endpoint": "/basket/2", "actor": "owner"}),
        json.dumps({"status_code": 200, "method": "GET", "endpoint": "/basket/3", "actor": "unknown"}),
    ]), encoding="utf-8")
    seeds = _seed_probes(str(trace), {"owner", "attacker"}, 10)
    assert [(probe.actor, probe.path) for probe in seeds] == [("owner", "/basket/1")]
