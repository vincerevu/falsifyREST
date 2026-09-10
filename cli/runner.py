from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from cli.session import RunConfig
from cli.report import write_markdown_report
from cli.recipe_synthesis import synthesize
from cli.ui.live import live_status
from adapters.factory import adapter_from_config
from adapters.capture_proxy import CaptureProxy
from adapters.evomaster_provider import EvoMasterProvider
from adapters.proxy import ProxyTraceImporter
from core.models import Probe
from experiments.juiceshop_benchmark_runner import analyze
from experiments.recipe_runner import run_recipes_with_adapter
from experiments.target_runner import run_with_adapter
from schema import parse_operations


@dataclass
class RunResult:
    openapi_path: str
    operation_count: int
    analysis: dict | None = None
    live: dict | None = None
    findings: list[dict] | None = None
    report_path: str | None = None


def _seed_probes(trace_path: str, actor_names: set[str], limit: int) -> list[Probe]:
    """Reuse successful captured requests as concrete control seeds for live search."""
    probes: list[Probe] = []
    seen: set[tuple] = set()
    for trace in ProxyTraceImporter().load(trace_path):
        for observation in trace.observations:
            if observation.actor not in actor_names or not 200 <= observation.status_code < 300:
                continue
            body = observation.request_body or None
            key = (observation.actor, observation.method, observation.endpoint, json.dumps(body, sort_keys=True, default=str))
            if key in seen:
                continue
            seen.add(key)
            probes.append(Probe(f"captured:{len(probes)}", observation.actor, observation.method, observation.endpoint, body))
            if len(probes) >= limit:
                return probes
    return probes


def _security_findings(live_results: list[dict]) -> list[dict]:
    """Flatten only validated security witnesses for concise terminal reporting."""
    findings: list[dict] = []
    for experiment in live_results:
        baseline = experiment["baseline"]
        for outcome in experiment["outcomes"]:
            if outcome.get("classification") != "SECURITY_RELEVANT_WITNESS":
                continue
            witness = outcome.get("witness", {})
            treatment_steps = witness.get("treatment", {}).get("steps", [])
            treatment = treatment_steps[-1].get("probe", {}) if treatment_steps else {}
            oracle = witness.get("oracle_evidence", {})
            effect = oracle.get("treatment_effect", {})
            findings.append({
                "hypothesis": outcome.get("candidate_id", "unknown"),
                "endpoint": f"{baseline['method']} {baseline['path']}",
                "control_actor": baseline["actor"],
                "treatment_actor": treatment.get("actor", "unknown"),
                "status": oracle.get("response_status", "unknown"),
                "effect": effect.get("reason", "protected effect observed"),
            })
    return findings


def _resolve_openapi(config: RunConfig) -> Path:
    source = config.target.openapi
    output = Path(config.output_dir)
    if config.target.openapi_source == "file" or (config.target.openapi_source == "auto" and Path(source).exists()):
        path = Path(source)
        if not path.exists():
            raise ValueError(f"OpenAPI file does not exist: {path}")
        return path
    url = source if config.target.openapi_source == "url" else f"{config.target.base_url.rstrip('/')}/openapi.json"
    try:
        with urlopen(url, timeout=10) as response:
            payload = response.read()
    except OSError as error:
        raise ValueError(f"Cannot retrieve OpenAPI document from {url}: {error}") from error
    if payload.lstrip().startswith(b"<"):
        raise ValueError(f"OpenAPI URL returned HTML, not an OpenAPI document: {url}. Point --openapi at the raw JSON/YAML spec, not a Swagger UI page.")
    output.mkdir(parents=True, exist_ok=True)
    path = output / "resolved-openapi.json"
    path.write_bytes(payload)
    return path


def _configure_llm(config: RunConfig) -> None:
    provider = config.llm.provider if config.llm.mode != "rule-only" else "disabled"
    os.environ["FALSIFYREST_LLM_PROVIDER"] = provider
    if config.llm.model:
        os.environ["FALSIFYREST_LLM_MODEL"] = config.llm.model
    if config.llm.base_url:
        os.environ["FALSIFYREST_LLM_BASE_URL"] = config.llm.base_url
    if config.llm.api_key_env:
        os.environ["FALSIFYREST_LLM_API_KEY"] = config.llm.api_key or os.environ.get(config.llm.api_key_env, "")


def _validate_llm(config: RunConfig) -> None:
    if config.llm.mode == "rule-only" or config.llm.provider == "disabled":
        return
    if not config.llm.base_url or not config.llm.model:
        raise ValueError("LLM prior mode requires both an LLM base URL and model")
    request_url = f"{config.llm.base_url.rstrip('/')}/models"
    try:
        headers = {}
        if config.llm.api_key_env:
            key = config.llm.api_key or os.environ.get(config.llm.api_key_env, "")
            if not key:
                raise ValueError(f"LLM API key environment variable is not set: {config.llm.api_key_env}")
            headers["Authorization"] = f"Bearer {key}"
        with urlopen(Request(request_url, headers=headers), timeout=5) as response:
            if not 200 <= response.status < 300:
                raise ValueError(f"LLM model endpoint returned HTTP {response.status}")
    except OSError as error:
        raise ValueError(f"Cannot connect to configured LLM at {request_url}: {error}") from error


def _capture_with_evomaster(config: RunConfig, openapi: Path) -> Path:
    """Generic exploration orchestration; authentication remains in TargetAdapter."""
    if not config.exploration.evomaster_jar:
        raise ValueError("EvoMaster exploration requires exploration.evomaster_jar")
    jar = Path(config.exploration.evomaster_jar)
    if not jar.is_file():
        raise ValueError(f"EvoMaster JAR does not exist: {jar}")
    trace = Path(config.exploration.trace_path or Path(config.output_dir) / "exploration.jsonl")
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.unlink(missing_ok=True)
    adapter = adapter_from_config(config)
    adapter.setup()
    proxy = CaptureProxy(config.target.base_url, trace)
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer(("127.0.0.1", config.exploration.proxy_port), proxy.handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        adapter.seed_exploration(f"http://127.0.0.1:{config.exploration.proxy_port}")
        actor_names = [actor.name for actor in config.actors] or ["anonymous"]
        for actor_name in actor_names:
            headers = [] if actor_name == "anonymous" else adapter.exploration_headers_for(actor_name)
            EvoMasterProvider(
                jar, str(openapi), f"http://127.0.0.1:{config.exploration.proxy_port}",
                Path(config.output_dir) / "evomaster" / actor_name,
                config.exploration.max_time, headers,
            ).run()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        adapter.reset()
    if not trace.is_file() or trace.stat().st_size == 0:
        raise RuntimeError("EvoMaster completed without capturing HTTP traffic; see output/evomaster for its logs")
    return trace


def run(config: RunConfig) -> RunResult:
    """Validate config and invoke only generic analysis; adapters own live execution."""
    _configure_llm(config)
    _validate_llm(config)
    with live_status("Resolving and parsing OpenAPI..."):
        openapi = _resolve_openapi(config)
        operation_count = len(parse_operations(openapi))
    result = RunResult(str(openapi), operation_count)
    trace_path: Path | None = None
    if config.exploration.provider == "evomaster":
        with live_status("Capturing authenticated exploration traffic with EvoMaster..."):
            trace_path = _capture_with_evomaster(config, openapi)
    elif config.exploration.provider == "trace":
        if not config.exploration.trace_path:
            raise ValueError("Existing-trace mode requires exploration.trace_path")
        trace_path = Path(config.exploration.trace_path)
        if not trace_path.is_file():
            raise ValueError(
                f"Trace file does not exist: {trace_path}. Set exploration.provider: evomaster to capture one automatically."
            )
    if trace_path is not None:
        with live_status("Importing trace and synthesizing hypotheses...") as analysis_status:
            runtime_config = Path(config.output_dir) / "runtime-config.json"
            runtime_config.parent.mkdir(parents=True, exist_ok=True)
            runtime_config.write_text(json.dumps({"target": {"openapi": str(openapi)}}, indent=2), encoding="utf-8")
            report, hypotheses, _ = analyze(runtime_config, trace_path)
            target_operations = sorted({item.target_operation for item in hypotheses if item.target_operation})
            synthesis = synthesize(
                config, openapi, trace_path, target_operations=target_operations,
                progress=analysis_status.update,
            )
            structural_repairs = []
            for attempt in range(config.recipe_synthesis.max_repairs if config.recipe_synthesis.enabled else 0):
                if not synthesis.rejected:
                    break
                repaired = synthesize(
                    config, openapi, trace_path, synthesis.rejected, synthesis.candidates,
                    target_operations, progress=analysis_status.update,
                )
                structural_repairs.append({"attempt": attempt + 1, "proposed": repaired.proposed,
                                           "accepted": sorted(repaired.recipes), "rejected": repaired.rejected})
                before = len(synthesis.recipes)
                synthesis.proposed.extend(name for name in repaired.proposed if name not in synthesis.proposed)
                synthesis.candidates.update(repaired.candidates)
                synthesis.recipes.update(repaired.recipes)
                for name in repaired.recipes:
                    synthesis.rejected.pop(name, None)
                synthesis.rejected.update(repaired.rejected)
                if len(synthesis.recipes) == before:
                    break
            config.resources = {**synthesis.recipes, **config.resources}
            result.analysis = {
                "report": asdict(report), "hypotheses": len(hypotheses),
                "recipe_synthesis": {"proposed": synthesis.proposed, "accepted": sorted(synthesis.recipes),
                                     "rejected": synthesis.rejected, "cache": synthesis.cache_path,
                                     "repairs": structural_repairs},
            }
            if config.live.enabled:
                with live_status("Preparing target adapter and executing live counterexamples...") as active_status:
                    adapter = adapter_from_config(config)
                    recipe_coverage: dict | None = None
                    if config.resources:
                        recipe_run = run_recipes_with_adapter(hypotheses, config.resources, adapter, config.budget)
                        live_results = list(recipe_run.results)
                        provisioned = list(recipe_run.provisioned)
                        skipped = {**synthesis.rejected, **recipe_run.skipped}
                        repairs = []
                        for attempt in range(config.recipe_synthesis.max_repairs if config.recipe_synthesis.enabled else 0):
                            if not skipped:
                                break
                            repaired = synthesize(
                                config, openapi, trace_path, skipped,
                                {name: config.resources.get(name, {}) for name in skipped}, target_operations,
                                progress=active_status.update,
                            )
                            repairs.append({"attempt": attempt + 1, "proposed": repaired.proposed,
                                            "accepted": sorted(repaired.recipes), "rejected": repaired.rejected})
                            if not repaired.recipes:
                                break
                            rerun = run_recipes_with_adapter(hypotheses, repaired.recipes, adapter, config.budget)
                            live_results.extend(rerun.results)
                            provisioned.extend(name for name in rerun.provisioned if name not in provisioned)
                            for name in repaired.recipes:
                                skipped.pop(name, None)
                            skipped.update(rerun.skipped)
                        seed_count = len(provisioned)
                        recipe_coverage = {"provisioned": provisioned, "skipped": skipped, "repairs": repairs}
                    elif config.recipe_synthesis.enabled:
                        live_results = []
                        seed_count = 0
                        recipe_coverage = {
                            "provisioned": [], "skipped": synthesis.rejected or {"synthesis": "LLM produced no structurally valid recipes"},
                            "repairs": [],
                        }
                    else:
                        seeds = _seed_probes(str(trace_path), {actor.name for actor in config.actors}, config.live.max_seeds)
                        if not seeds:
                            raise ValueError("No successful captured seed requests match configured actor names")
                        live_results = run_with_adapter(hypotheses, seeds, adapter, max(1, config.budget // len(seeds)))
                        seed_count = len(seeds)
                    result.live = {
                        "seeds": seed_count, "experiments": len(live_results),
                        "outcomes": sum(len(item["outcomes"]) for item in live_results),
                    }
                    if recipe_coverage is not None:
                        result.live["recipe_coverage"] = recipe_coverage
                    artifact = Path(config.output_dir) / "live-results.json"
                    artifact.write_text(json.dumps(live_results, indent=2, default=str), encoding="utf-8")
                    result.live["artifact"] = str(artifact)
                    result.findings = _security_findings(live_results)
    elif config.live.enabled:
        raise ValueError("Live mode requires exploration.provider: trace and a captured normalized trace")
    result.report_path = str(write_markdown_report(config, result))
    return result
