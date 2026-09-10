"""Target-neutral provisioning of live seeds from declarative resource recipes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from adapters.target import TargetAdapter
from core.models import Probe
from experiments.target_runner import run_with_adapter
from inference.hypothesis import PolicyHypothesis

_BINDING = re.compile(r"\$\{([^}]+)\}")


@dataclass
class RecipeRun:
    results: list[dict]
    provisioned: list[str]
    skipped: dict[str, str]


def _lookup(context: dict[str, Any], expression: str) -> Any:
    value: Any = context
    for part in expression.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(expression)
        value = value[part]
    return value


def _bind(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _bind(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [_bind(item, context) for item in value]
    if not isinstance(value, str):
        return value
    full = _BINDING.fullmatch(value)
    if full:
        return _lookup(context, full.group(1))
    return _BINDING.sub(lambda match: str(_lookup(context, match.group(1))), value)


def _json_path(value: Any, expression: str) -> Any:
    current = value
    for part in expression.removeprefix("$").removeprefix(".").split("."):
        if part:
            if not isinstance(current, dict) or part not in current:
                raise KeyError(expression)
            current = current[part]
    return current


def _request(recipe_id: str, step_id: str, item: dict, context: dict) -> Probe:
    request = item["request"]
    return Probe(
        f"recipe:{recipe_id}:{step_id}", request["actor"], request["method"],
        _bind(request["path"], context), _bind(request.get("body"), context),
    )


def run_recipes_with_adapter(hypotheses: list[PolicyHypothesis], recipes: dict[str, dict], adapter: TargetAdapter,
                             budget_per_seed: int) -> RecipeRun:
    """Provision, validate, and clean up recipes without target-specific testing logic."""
    results: list[dict] = []
    provisioned: list[str] = []
    skipped: dict[str, str] = {}
    adapter.setup()
    try:
        for recipe_id, recipe in recipes.items():
            context = {**adapter.binding_context(), "resource": {}}
            cleanup: list[Probe] = []
            try:
                for index, step in enumerate(recipe.get("setup", [])):
                    probe = _request(recipe_id, f"setup:{index}", step, context)
                    observation = adapter.execute(probe)
                    if not 200 <= observation.status_code < 300:
                        raise RuntimeError(f"setup returned HTTP {observation.status_code}")
                    for name, expression in step["request"].get("save", {}).items():
                        context["resource"][name] = _json_path(observation.response_body, expression)
                baseline = _request(recipe_id, "baseline", {"request": recipe["baseline"]}, context)
                cleanup = [_request(recipe_id, f"cleanup:{index}", step, context) for index, step in enumerate(recipe.get("cleanup", []))]
                live = run_with_adapter(
                    hypotheses, [baseline], adapter, budget_per_seed,
                    manage_lifecycle=False, seeds_prepared=True,
                )
                if live:
                    results.extend(live)
                    provisioned.append(recipe_id)
                else:
                    skipped[recipe_id] = "no relevant hypothesis or feasible counterfactual"
            except (KeyError, RuntimeError, ValueError) as error:
                skipped[recipe_id] = str(error)
            finally:
                for probe in reversed(cleanup):
                    try:
                        adapter.execute(probe)
                    except Exception:
                        pass
    finally:
        adapter.reset()
    return RecipeRun(results, provisioned, skipped)
