from core.models import Observation
from resources.tracker import ResourceTracker

from .models import Evidence


def extract_evidence(observation: Observation, tracker: ResourceTracker | None = None, source_trace: str = "trace", evaluation_context: dict | None = None) -> Evidence:
    """Convert one real execution into evidence; it makes no policy assertion."""
    resource_id = next(iter(observation.extracted_ids.values()), None)
    resource_type = str(observation.features.get("resource_type", "resource"))
    relation = None
    body = observation.body if isinstance(observation.body, dict) else {}
    owner_id = body.get("owner") or body.get("ownerId") or observation.features.get("owner") or observation.features.get("owner_id")
    if tracker is not None and resource_id is not None:
        try:
            resource = tracker.get(resource_type, str(resource_id))
            relation = "owner" if resource.owner == observation.actor else "foreign"
            owner_id = resource.owner
        except KeyError:
            pass
    outcome = "SUCCESS" if 200 <= observation.status_code < 300 else "DENIED" if observation.status_code in {401, 403, 404, 409} else "ERROR"
    operation_id = str(observation.features.get("operation_id", f"{observation.method} {observation.endpoint}"))
    return Evidence(
        id=f"{source_trace}:{observation.timestamp}:{operation_id}:{observation.actor}",
        operation_id=operation_id, resource_type=resource_type, resource_id=str(resource_id) if resource_id is not None else None,
        actor_id=observation.actor, actor_relation=relation, resource_owner_id=owner_id, pre_state=dict(observation.state_before), post_state=dict(observation.state_after),
        outcome=outcome, status_code=observation.status_code, request_features={**observation.request_path, **observation.request_query, **observation.request_body},
        response_features=dict(observation.features), history=dict((evaluation_context or {}).get("history", {})), source_trace=source_trace,
    )
