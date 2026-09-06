from dataclasses import dataclass, field
from typing import Any

from .models import Evidence


@dataclass(frozen=True)
class EvaluationContext:
    """The single predicate-evaluation schema used by selection and belief induction."""
    actor: dict[str, Any] = field(default_factory=dict)
    resource: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    history: dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {"actor": dict(self.actor), "resource": dict(self.resource), "state": dict(self.state), "history": dict(self.history)}


def context_from_evidence(item: Evidence) -> EvaluationContext:
    owner_id = item.resource_owner_id
    if owner_id is None and item.actor_relation == "owner":
        owner_id = item.actor_id
    if owner_id is None and item.actor_relation == "foreign":
        owner_id = "<foreign-owner>"
    return EvaluationContext(
        actor={"id": item.actor_id, "authenticated": item.actor_id != "anonymous"},
        resource={"owner_id": owner_id}, state=dict(item.pre_state), history=dict(item.history),
    )
