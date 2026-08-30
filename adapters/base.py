from abc import ABC, abstractmethod

from execution.trace_store import Trace


class SequenceProvider(ABC):
    @abstractmethod
    def generate_sequences(self, target_operations=None) -> list[Trace]:
        """Return seed traces; the policy algorithm never depends on provider internals."""
