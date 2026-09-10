"""LLM-assisted recipe proposal outside the deterministic detection core."""
from __future__ import annotations

import json
import os
import re
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen
from urllib.error import URLError

import yaml

from schema import parse_operations


@dataclass
class SynthesisResult:
    recipes: dict[str, dict] = field(default_factory=dict)
    proposed: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)
    candidates: dict[str, dict] = field(default_factory=dict)
    cache_path: str | None = None


def _chat_content(raw: str) -> str:
    try:
        records = [json.loads(raw)]
    except json.JSONDecodeError:
        records = []
        for line in raw.splitlines():
            line = line.removeprefix("data:").strip()
            if line and line != "[DONE]":
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if not records:
        raise ValueError("LLM returned no parseable JSON response")
    complete = next((item for item in reversed(records) if item.get("choices") and item["choices"][0].get("message")), None)
    if complete:
        return complete["choices"][0]["message"].get("content", "")
    return "".join(item.get("choices", [{}])[0].get("delta", {}).get("content", "") for item in records if item.get("choices"))


def _operation_matches(method: str, recipe_path: str, operations) -> bool:
    candidate = re.sub(r"\$\{[^}]+\}", "VALUE", str(recipe_path).rstrip("/"))
    for operation in operations:
        pattern = re.sub(r"\{[^}]+\}", "[^/]+", operation.path.rstrip("/"))
        if operation.method.upper() == str(method).upper() and re.fullmatch(pattern, candidate):
            return True
    return False


def _validate_recipe(recipe: dict, operations) -> str | None:
    if not isinstance(recipe, dict) or not isinstance(recipe.get("baseline"), dict):
        return "missing baseline request"
    requests = [step.get("request", {}) for step in recipe.get("setup", [])]
    requests += [recipe["baseline"]]
    requests += [step.get("request", {}) for step in recipe.get("cleanup", [])]
    for request in requests:
        if not request.get("actor"):
            return "request is missing actor"
        if not _operation_matches(request.get("method", ""), request.get("path", ""), operations):
            return f"operation absent from OpenAPI: {request.get('method')} {request.get('path')}"
    return None


def _normalize_recipe(recipe: dict, default_actor: str) -> dict:
    """Fill schema defaults that are unambiguous and target-independent."""
    if not isinstance(recipe, dict):
        return recipe
    for step in recipe.get("setup", []):
        if isinstance(step, dict) and isinstance(step.get("request"), dict):
            step["request"].setdefault("actor", default_actor)
    if isinstance(recipe.get("baseline"), dict):
        recipe["baseline"].setdefault("actor", default_actor)
    for step in recipe.get("cleanup", []):
        if isinstance(step, dict) and isinstance(step.get("request"), dict):
            step["request"].setdefault("actor", default_actor)
    return recipe


def _trace_examples(trace_path: str | Path | None, limit: int = 20) -> list[dict]:
    if not trace_path or not Path(trace_path).is_file():
        return []
    examples, seen = [], set()
    with Path(trace_path).open(encoding="utf-8") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not 200 <= int(item.get("status_code", 0)) < 300:
                continue
            key = (item.get("method"), item.get("endpoint"))
            if key in seen:
                continue
            seen.add(key)
            request_body, response_body = item.get("request_body"), item.get("response_body")
            examples.append({
                "method": key[0], "path": key[1], "actor": item.get("actor"),
                "request_fields": sorted(request_body) if isinstance(request_body, dict) else [],
                "response_fields": sorted(response_body) if isinstance(response_body, dict) else [],
            })
            if len(examples) >= limit:
                break
    return examples


def synthesize(config, openapi: Path, trace_path: str | Path | None = None,
               failures: dict[str, str] | None = None, previous: dict[str, dict] | None = None,
               target_operations: list[str] | None = None,
               progress: Callable[[str], None] | None = None) -> SynthesisResult:
    if not config.recipe_synthesis.enabled:
        return SynthesisResult()
    if config.llm.provider == "disabled" or not config.llm.base_url or not config.llm.model:
        raise ValueError("Recipe synthesis requires an enabled OpenAI-compatible LLM and model")
    operations = parse_operations(openapi)
    operation_names = [f"{item.method} {item.path}" for item in operations]
    targets = target_operations or operation_names
    batch_size = max(1, config.recipe_synthesis.batch_size)
    batches = [targets[index:index + batch_size] for index in range(0, len(targets), batch_size)]
    key = config.llm.api_key or os.environ.get(config.llm.api_key_env or "", "")
    if not key:
        raise ValueError("Recipe synthesis requires an API key")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    examples = _trace_examples(trace_path)
    result = SynthesisResult()
    for batch_index, batch in enumerate(batches):
        if batch_index and config.recipe_synthesis.batch_delay:
            time.sleep(config.recipe_synthesis.batch_delay)
        if progress:
            progress(f"LLM recipe synthesis batch {batch_index + 1}/{len(batches)} ({len(batch)} target operations)...")
        task = {
            "task": "repair failed recipes" if failures else "generate executable resource lifecycle recipes",
            "rules": ["Return JSON only with a resources map", "use only listed operations and actors",
                      "generate one uniquely named recipe per target operation when a concrete lifecycle can be constructed",
                      "use ${actor.NAME.FIELD} and ${resource.FIELD} bindings", "save created IDs with JSONPath",
                      "include cleanup when possible", "never make vulnerability verdicts"],
            "actors": [actor.name for actor in config.actors],
            "available_operations": sorted(set(batch + [name for name in operation_names if name.startswith(("POST ", "GET "))]))[:80],
            "target_operations": batch, "successful_trace_examples": examples,
            "runtime_bindings": ["actor.<name>.basket_id"], "previous_recipes": previous or {},
            "runtime_failures": failures or {},
            "output_shape": {"resources": {"operation_recipe_name": {"setup": [{"request": {"actor": "owner", "method": "POST", "path": "/path", "body": {}, "save": {"resource_id": "$.data.id"}}}], "baseline": {"actor": "owner", "method": "GET", "path": "/path/${resource.resource_id}"}, "cleanup": []}}},
        }
        payload = json.dumps({
            "model": config.llm.model, "messages": [{"role": "user", "content": json.dumps(task)}],
            "temperature": 0, "stream": False, "response_format": {"type": "json_object"},
        }).encode()
        content = None
        last_error = None
        for _attempt in range(config.recipe_synthesis.request_retries + 1):
            try:
                with urlopen(
                    Request(config.llm.base_url.rstrip("/") + "/chat/completions", data=payload, headers=headers),
                    timeout=config.recipe_synthesis.request_timeout,
                ) as response:
                    content = _chat_content(response.read().decode("utf-8", errors="replace"))
                break
            except (TimeoutError, socket.timeout, URLError) as error:
                last_error = error
                if config.recipe_synthesis.retry_backoff:
                    time.sleep(config.recipe_synthesis.retry_backoff)
        if content is None:
            result.rejected[f"batch_{batch_index}"] = f"LLM request failed after retries: {last_error}"
            continue
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            result.rejected[f"batch_{batch_index}"] = "LLM response did not contain JSON"
            continue
        try:
            proposed = json.loads(match.group(0)).get("resources", {})
        except json.JSONDecodeError as error:
            result.rejected[f"batch_{batch_index}"] = f"invalid JSON: {error}"
            continue
        result.proposed.extend(proposed)
        for name, recipe in proposed.items():
            recipe = _normalize_recipe(recipe, config.actors[0].name if config.actors else "anonymous")
            result.candidates[name] = recipe
            reason = _validate_recipe(recipe, operations)
            if reason:
                result.rejected[name] = reason
            else:
                result.recipes[name] = recipe
    cache = Path(config.output_dir) / "llm-recipe-candidates.yaml"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(yaml.safe_dump({"candidates": result.candidates, "accepted": result.recipes, "rejected": result.rejected}, sort_keys=False), encoding="utf-8")
    result.cache_path = str(cache)
    return result
