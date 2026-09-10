from dataclasses import dataclass, field

from .predicate import Predicate


@dataclass
class PolicyHypothesis:
    id: str
    subject_relation: str
    action: str
    resource_type: str
    preconditions: list[str] = field(default_factory=list)
    expected: str = "DENY"
    confidence: float = 0.0
    support: int = 0
    violations_tested: int = 0
    family: str = "ownership"
    target_operation: str | None = None
    resource: str | None = None
    expected_observation: str = "DENY"
    evidence: list[str] = field(default_factory=list)
    status: str = "UNTESTED"
    predicates: list[Predicate] = field(default_factory=list)
    expected_effect: str = "PROTECTED_EFFECT"
    support_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    protected_fields: set[str] = field(default_factory=set)
    relevant_dimensions: set[str] = field(default_factory=set)
    applicable_operators: set[str] = field(default_factory=set)
    supporting_trace_ids: list[str] = field(default_factory=list)
    falsification_condition: str | None = None
    required_changed_dimensions: set[str] = field(default_factory=set)
    required_any_changed_dimensions: set[str] = field(default_factory=set)
    required_preserved_dimensions: set[str] = field(default_factory=set)
    required_context_values: dict[str, object] = field(default_factory=dict)
    required_distinct_context_fields: list[tuple[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Family defaults are declared once on the hypothesis, not in the oracle."""
        defaults = {
            "ownership": ({"actor"}, {"operation", "resource"}, {}, [("actor.id", "resource.owner_id")]),
            "authorization": ({"actor"}, {"operation"}, {"actor.authenticated": False}, []),
            "state-transition": (set(), {"operation"}, {}, []),
            "replay": ({"occurrence_count"}, {"operation", "request_shape"}, {}, []),
        }
        changed, preserved, values, distinct = defaults.get(self.family, (set(), {"operation"}, {}, []))
        if not self.required_changed_dimensions:
            self.required_changed_dimensions = set(changed)
        if self.family == "state-transition" and not self.required_any_changed_dimensions:
            self.required_any_changed_dimensions = {"sequence", "order"}
        if not self.required_preserved_dimensions:
            self.required_preserved_dimensions = set(preserved)
        if not self.required_context_values:
            self.required_context_values = dict(values)
        if not self.required_distinct_context_fields:
            self.required_distinct_context_fields = list(distinct)
        if not self.applicable_operators:
            compatibility_operators = {
                "ownership": {"actor_swap"},
                "authorization": {"actor_swap"},
                "state-transition": {"repeat"},
                "replay": {"repeat"},
            }
            self.applicable_operators = set(compatibility_operators.get(self.family, ()))

    def predict(self, context: dict) -> str:
        """A hypothesis predicts allow only when all known predicates hold."""
        results = [predicate.evaluate(context) for predicate in self.predicates]
        return "ALLOW" if results and all(result is True for result in results) else "DENY"

    @property
    def required_state(self) -> str | None:
        for condition in self.preconditions:
            if condition.startswith("status == "):
                return condition.removeprefix("status == ")
        return None

    def is_applicable_operator(self, operator: object) -> bool:
        """Keep family inference separate from concrete trace mutation."""
        name = getattr(operator, "name", str(operator))
        return not self.applicable_operators or name in self.applicable_operators
