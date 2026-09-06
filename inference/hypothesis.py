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
