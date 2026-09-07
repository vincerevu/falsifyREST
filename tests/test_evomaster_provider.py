import subprocess
from pathlib import Path

from adapters.evomaster_provider import EvoMasterProvider
from adapters.proxy import ProxyTraceImporter


def test_evomaster_provider_passes_static_actor_headers(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    EvoMasterProvider("tool.jar", "openapi.json", "http://target", tmp_path, headers=["Authorization: Bearer token", "X-FalsifyREST-Actor: user_a"]).run()
    assert captured["command"][-4:] == ["--header0", "Authorization: Bearer token", "--header1", "X-FalsifyREST-Actor: user_a"]


def test_proxy_trace_importer_collapses_duplicate_actor_header(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text('{"status_code":200,"method":"GET","endpoint":"/x","actor":"user_a, user_a"}\n', encoding="utf-8")
    assert ProxyTraceImporter().load(trace)[0].observations[0].actor == "user_a"
