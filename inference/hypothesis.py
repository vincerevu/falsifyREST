from dataclasses import dataclass, field


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

    @property
    def required_state(self) -> str | None:
        for condition in self.preconditions:
            if condition.startswith("status == "):
                return condition.removeprefix("status == ")
        return None
