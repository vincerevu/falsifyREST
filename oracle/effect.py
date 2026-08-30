from dataclasses import dataclass
from typing import Any

from core.models import Observation


@dataclass(frozen=True)
class EffectResult:
    classification: str
    protected_effect: bool
    reason: str


def classify_effect(before: dict[str, Any], response: Observation, after: dict[str, Any], protected_field: str = "status") -> EffectResult:
    if response.status_code >= 500:
        return EffectResult("ERROR", False, "server error")
    if isinstance(response.response_body, dict) and response.response_body.get("error"):
        return EffectResult("DENIED", False, "explicit error response")
    if before.get(protected_field) != after.get(protected_field):
        return EffectResult("EFFECTIVE_SUCCESS", True, f"{protected_field} changed")
    if response.status_code in {401, 403, 404, 409}:
        return EffectResult("DENIED", False, f"HTTP {response.status_code}")
    return EffectResult("UNKNOWN", False, "no protected state change")


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
