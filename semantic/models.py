from dataclasses import dataclass, field

from schema.models import Operation


@dataclass
class SemanticOperation:
    operation: Operation
    resource: str
    action: str
    security_concepts: set[str] = field(default_factory=set)
    likely_invariants: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "rule"
    actor_fields: list[str] = field(default_factory=list)
    resource_id_fields: list[str] = field(default_factory=list)
    state_fields: list[str] = field(default_factory=list)
    relationship_fields: list[str] = field(default_factory=list)
    candidate_policy_families: set[str] = field(default_factory=set)
    family_sources: dict[str, set[str]] = field(default_factory=dict)
    family_confidence: dict[str, float] = field(default_factory=dict)

    def add_family(self, family: str, source: str, confidence: float) -> None:
        self.candidate_policy_families.add(family)
        self.family_sources.setdefault(family, set()).add(source)
        self.family_confidence[family] = max(self.family_confidence.get(family, 0.0), confidence)
        all_sources = {item for sources in self.family_sources.values() for item in sources}
        preferred_order = {"rule": 0, "llm": 1, "evidence": 2}
        self.source = "+".join(sorted(all_sources, key=lambda item: preferred_order.get(item, 99)))


@dataclass
class Relation:
    source: str
    relation: str
    target: str
    confidence: float = 0.0


@dataclass
class StateTransition:
    resource: str
    operation_id: str
    pre_state: str | None
    post_state: str | None
    support: int = 0


@dataclass
class APISemanticModel:
    operations: list[SemanticOperation] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    transitions: list[StateTransition] = field(default_factory=list)

    def by_resource(self, resource: str) -> list[SemanticOperation]:
        return [item for item in self.operations if item.resource == resource]
