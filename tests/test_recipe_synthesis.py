import json

import cli.recipe_synthesis as synthesis
from cli.session import LLMConfig, RecipeSynthesisConfig, RunConfig, TargetConfig


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def read(self):
        return self.payload


def test_synthesis_batches_targets_and_accepts_generic_bound_paths(tmp_path, monkeypatch):
    spec = tmp_path / "openapi.json"
    spec.write_text(json.dumps({"paths": {
        "/claims/{claimId}": {"get": {"operationId": "getClaim", "responses": {"200": {"description": "ok"}}}},
        "/orders/{orderId}": {"get": {"operationId": "getOrder", "responses": {"200": {"description": "ok"}}}},
    }}), encoding="utf-8")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(json.loads(request.data))
        target = json.loads(calls[-1]["messages"][0]["content"])["target_operations"][0]
        path = "/claims/${resource.id}" if "claims" in target else "/orders/${resource.id}"
        content = json.dumps({"resources": {target: {"baseline": {"actor": "owner", "method": "GET", "path": path}}}})
        return Response(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    monkeypatch.setattr(synthesis, "urlopen", fake_urlopen)
    config = RunConfig(
        TargetConfig("http://target", str(spec)),
        llm=LLMConfig(provider="openai", model="model", base_url="http://llm/v1", api_key="local"),
        recipe_synthesis=RecipeSynthesisConfig(enabled=True, batch_size=1, batch_delay=0), output_dir=str(tmp_path / "output"),
    )
    result = synthesis.synthesize(config, spec, target_operations=["GET /claims/{claimId}", "GET /orders/{orderId}"])
    assert len(calls) == 2
    assert len(result.recipes) == 2
    assert not result.rejected


def test_synthesis_records_timed_out_batch_and_continues(tmp_path, monkeypatch):
    spec = tmp_path / "openapi.json"
    spec.write_text(json.dumps({"paths": {
        "/a/{id}": {"get": {"operationId": "a", "responses": {"200": {"description": "ok"}}}},
        "/b/{id}": {"get": {"operationId": "b", "responses": {"200": {"description": "ok"}}}},
    }}), encoding="utf-8")
    calls = 0

    def fake_urlopen(_request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("slow batch")
        content = json.dumps({"resources": {"b": {"baseline": {"actor": "owner", "method": "GET", "path": "/b/${resource.id}"}}}})
        return Response(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    monkeypatch.setattr(synthesis, "urlopen", fake_urlopen)
    config = RunConfig(
        TargetConfig("http://target", str(spec)),
        llm=LLMConfig(provider="openai", model="model", base_url="http://llm/v1", api_key="local"),
        recipe_synthesis=RecipeSynthesisConfig(enabled=True, batch_size=1, request_retries=0, retry_backoff=0, batch_delay=0),
        output_dir=str(tmp_path / "output"),
    )
    result = synthesis.synthesize(config, spec, target_operations=["GET /a/{id}", "GET /b/{id}"])
    assert "batch_0" in result.rejected
    assert "b" in result.recipes
