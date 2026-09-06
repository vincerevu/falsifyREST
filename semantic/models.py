from dataclasses import dataclass, field

from schema.models import Operation


@dataclass
class SemanticOperation:
    operation: Operation
    resource: str
    action: str
    static_facts: dict[str, object] = field(default_factory=dict)
    actor_fields: list[str] = field(default_factory=list)
    resource_id_fields: list[str] = field(default_factory=list)
    state_fields: list[str] = field(default_factory=list)
    relationship_fields: list[str] = field(default_factory=list)
    family_priors: dict[str, float] = field(default_factory=dict)
    prior_source: str = "uniform"

    def family_prior(self, family: str) -> float:
        return self.family_priors.get(family, 0.5)

    def set_family_prior(self, family: str, value: float, source: str = "llm") -> None:
        self.family_priors[family] = min(1.0, max(0.0, float(value)))
        self.prior_source = source


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
