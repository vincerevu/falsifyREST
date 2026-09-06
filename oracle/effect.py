from dataclasses import dataclass, field
from typing import Any

from core.models import Observation


@dataclass(frozen=True)
class EffectResult:
    classification: str
    protected_effect: bool
    reason: str
    changed_fields: dict[str, tuple[Any, Any]] = field(default_factory=dict)


def diff_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    return {key: (before.get(key), after.get(key)) for key in set(before) | set(after) if before.get(key) != after.get(key)}


def classify_effect(before: dict[str, Any], response: Observation, after: dict[str, Any], protected_fields: set[str] | None = None) -> EffectResult:
    changes = diff_snapshots(before, after)
    protected = set(protected_fields or ())
    protected_changes = {key: value for key, value in changes.items() if key in protected}
    if protected_changes:
        return EffectResult("EFFECTIVE_SUCCESS", True, f"protected fields changed: {', '.join(sorted(protected_changes))}", protected_changes)
    if response.status_code >= 500:
        return EffectResult("ERROR", False, "server error", changes)
    if isinstance(response.response_body, dict) and response.response_body.get("error"):
        return EffectResult("DENIED", False, "explicit error response", changes)
    if response.status_code in {401, 403, 404, 409}:
        return EffectResult("DENIED", False, f"HTTP {response.status_code}", changes)
    return EffectResult("NO_EFFECT", False, "no protected state change", changes)


def classify_disclosure(response: Observation, expected_resource_id: str) -> EffectResult:
    """A protected read succeeds only when the response returns non-error resource data."""
    body = response.response_body
    if response.status_code in {401, 403, 404, 409}:
        return EffectResult("DENIED", False, f"HTTP {response.status_code}")
    if not 200 <= response.status_code < 300:
        return EffectResult("ERROR" if response.status_code >= 500 else "UNKNOWN", False, f"HTTP {response.status_code}")
    if isinstance(body, dict) and body.get("error"):
        return EffectResult("DENIED", False, "explicit error response")
    serialized = str(body)
    if expected_resource_id in serialized or isinstance(body, (dict, list)):
        return EffectResult("EFFECTIVE_DISCLOSURE", True, "protected resource data returned")
    return EffectResult("UNKNOWN", False, "success status without recognizable resource data")
