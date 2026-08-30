from core.models import Observation
from .resource import Resource


class ResourceTracker:
    def __init__(self):
        self._resources: dict[str, Resource] = {}

    def observe(self, observation: Observation) -> list[Resource]:
        body = observation.body if isinstance(observation.body, dict) else {}
        resource_id = observation.extracted_ids.get("resource_id") or observation.extracted_ids.get("order_id") or body.get("id")
        resource_type = observation.features.get("resource_type") or body.get("type") or "order"
        if resource_id is None:
            return []
        key = f"{resource_type}:{resource_id}"
        resource = self._resources.get(key, Resource(str(resource_type), str(resource_id)))
        if observation.method == "POST" and observation.endpoint.rstrip("/").endswith("orders"):
            resource.creator = observation.actor
        owner = body.get("owner") or body.get("ownerId") or observation.features.get("owner")
        if owner is not None:
            resource.owner = str(owner)
        elif resource.creator:
            resource.owner = resource.creator
        resource.attributes.update(body)
        resource.attributes.update(observation.state_after)
        self._resources[key] = resource
        return [resource]

    def get(self, resource_type: str, resource_id: str) -> Resource:
        return self._resources[f"{resource_type}:{resource_id}"]

    def all(self) -> list[Resource]:
        return list(self._resources.values())
