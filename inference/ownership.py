from collections import defaultdict
import re

from execution.trace_store import TraceStore
from resources.tracker import ResourceTracker
from .hypothesis import PolicyHypothesis


def infer_ownership_policies(trace_store: TraceStore, tracker: ResourceTracker) -> list[PolicyHypothesis]:
    successful = defaultdict(list)
    for observation in trace_store.observations():
        if not 200 <= observation.status_code < 300:
            continue
        resource_id = observation.extracted_ids.get("resource_id") or observation.extracted_ids.get("order_id")
        if resource_id is None:
            continue
        resource_type = observation.features.get("resource_type", "order")
        try:
            resource = tracker.get(resource_type, str(resource_id))
        except KeyError:
            continue
        if resource.owner == observation.actor:
            template = re.sub(r"/\d+(?=/|$)", "/{id}", observation.endpoint)
            successful[(observation.method, template, resource_type)].append((observation, resource))

    hypotheses = []
    for index, ((method, endpoint, resource_type), evidence) in enumerate(successful.items(), start=1):
        if len(evidence) < 1:
            continue
        statuses = {observation.state_before.get("status") or resource.attributes.get("status") for observation, resource in evidence}
        preconditions = [f"status == {next(iter(statuses))}"] if len(statuses) == 1 and next(iter(statuses)) else []
        hypotheses.append(PolicyHypothesis(
            id=f"ownership-{index}", subject_relation="actor == resource.owner",
            action=f"{method} {endpoint}", resource_type=resource_type,
            preconditions=preconditions, expected="DENY", confidence=min(0.95, 0.55 + 0.1 * len(evidence)), support=len(evidence),
        ))
    return hypotheses
