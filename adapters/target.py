"""Target boundary for API-agnostic counterfactual testing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from core.models import Observation, Probe
from violation.counterfactual import CounterfactualContext


class TargetAdapter(Protocol):
    """Target-specific auth/setup mechanics; generic modules depend only on this contract."""
    supports_fresh_control: bool

    def setup(self) -> None:
        """Prepare identities, authentication and fixtures before testing."""

    def prepare_seed(self, baseline: Probe) -> Probe | None:
        """Rebind a captured seed to live target resources, or reject it."""

    def exploration_headers_for(self, actor_name: str) -> list[str]:
        """Return safe runtime headers for a target explorer, after setup()."""

    def seed_exploration(self, proxy_url: str) -> list[Probe]:
        """Record target-owned control requests through an exploration proxy."""

    def binding_context(self) -> dict:
        """Return non-secret target facts for declarative resource recipes."""

    def context_for(self, baseline: Probe) -> CounterfactualContext: ...
    def execute(self, probe: Probe) -> Observation: ...
    def snapshot(self) -> dict: ...
    def protected_fields_for(self, baseline: Probe) -> set[str]: ...
    def reset(self) -> None: ...


@dataclass
class CallbackTargetAdapter:
    """Generic adapter for integrations that expose target mechanics as callbacks."""
    context_resolver: Callable[[Probe], CounterfactualContext]
    executor: Callable[[Probe], Observation]
    snapshotter: Callable[[], dict]
    protected_field_resolver: Callable[[Probe], set[str]]
    resetter: Callable[[], None] = lambda: None
    setupper: Callable[[], None] = lambda: None
    supports_fresh_control: bool = False

    def setup(self) -> None:
        self.setupper()

    def context_for(self, baseline: Probe) -> CounterfactualContext:
        return self.context_resolver(baseline)

    def prepare_seed(self, baseline: Probe) -> Probe | None:
        return baseline

    def exploration_headers_for(self, actor_name: str) -> list[str]:
        return []

    def seed_exploration(self, proxy_url: str) -> list[Probe]:
        return []

    def binding_context(self) -> dict:
        return {}

    def execute(self, probe: Probe) -> Observation:
        return self.executor(probe)

    def snapshot(self) -> dict:
        return self.snapshotter()

    def protected_fields_for(self, baseline: Probe) -> set[str]:
        return self.protected_field_resolver(baseline)

    def reset(self) -> None:
        self.resetter()
