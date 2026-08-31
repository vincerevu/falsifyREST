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
