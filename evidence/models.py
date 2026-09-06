from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StateObservation:
    resource_id: str
    resource_type: str
    actor_id: str
    operation_id: str
    state_before: dict[str, Any]
    state_after: dict[str, Any]
    status_code: int
    request_features: dict[str, Any] = field(default_factory=dict)
    response_features: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Evidence:
    id: str
    operation_id: str
    resource_type: str
    resource_id: str | None
    actor_id: str
    actor_relation: str | None
    pre_state: dict[str, Any]
    post_state: dict[str, Any]
    outcome: str
    status_code: int
    request_features: dict[str, Any] = field(default_factory=dict)
    response_features: dict[str, Any] = field(default_factory=dict)
    source_trace: str = "trace"
