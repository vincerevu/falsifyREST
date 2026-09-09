from abc import ABC, abstractmethod

from core.models import ExecutionTrace
from inference.hypothesis import PolicyHypothesis


class TransformationOperator(ABC):
    name: str
    affected_dimensions: frozenset[str] = frozenset()

    @abstractmethod
    def applicable(self, hypothesis: PolicyHypothesis, trace: ExecutionTrace, context: object) -> bool: ...

    @abstractmethod
    def apply(self, trace: ExecutionTrace, context: object) -> ExecutionTrace: ...
