from dataclasses import dataclass, field
from typing import Any

from core.models import Observation
from semantic.models import StateTransition


@dataclass
class ResourceState:
    resource_id: str
    values: dict[str, Any] = field(default_factory=dict)
    last_actor: str | None = None


class StateModel:
    """Observed state only; it does not fabricate undocumented lifecycle rules."""
    def __init__(self):
        self.resources: dict[str, ResourceState] = {}
        self.transitions: list[StateTransition] = []

    def observe(self, observation: Observation, resource: str) -> list[StateTransition]:
        identifiers = [str(value) for value in observation.extracted_ids.values()]
        identifiers.extend(observation.objects_read + observation.objects_created + observation.objects_modified)
        identifiers = list(dict.fromkeys(item for item in identifiers if item))
        created: list[StateTransition] = []
        for resource_id in identifiers:
            previous = self.resources.get(resource_id, ResourceState(resource_id))
            before = observation.state_before.get("status", previous.values.get("status"))
            after = observation.state_after.get("status", before)
            state = ResourceState(resource_id, {**previous.values, **observation.state_after}, observation.actor)
            self.resources[resource_id] = state
            if before != after:
                transition = StateTransition(resource, observation.endpoint, str(before) if before is not None else None, str(after), 1)
                self.transitions.append(transition)
                created.append(transition)
        return created
