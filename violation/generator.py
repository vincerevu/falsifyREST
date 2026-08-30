from dataclasses import dataclass

from actors.manager import ActorManager
from core.models import Probe
from inference.hypothesis import PolicyHypothesis
from resources.resource import Resource


@dataclass(frozen=True)
class Counterexample:
    hypothesis_id: str
    actor: str
    probe: Probe
    resource_key: str
    expected: str


def violate_ownership(hypothesis: PolicyHypothesis, successful_probe: Probe, resource: Resource, actors: ActorManager) -> Counterexample:
    if not resource.owner:
        raise ValueError("ownership counterexample requires a known resource owner")
    attacker = actors.other_than(resource.owner)
    path = successful_probe.path.replace("{id}", resource.id).replace("{resource_id}", resource.id)
    if resource.id not in path and "{" not in successful_probe.path:
        path = successful_probe.path.rstrip("/") + f"/{resource.id}"
    probe = Probe(f"counterexample-{hypothesis.id}", attacker.id, successful_probe.method, path, successful_probe.body, successful_probe.cost, successful_probe.risk)
    return Counterexample(hypothesis.id, attacker.id, probe, resource.key, hypothesis.expected)
