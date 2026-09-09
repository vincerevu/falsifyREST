"""Generic target adapter contract for API-agnostic counterfactual testing.

The core algorithm must not know how a concrete SUT authenticates users, creates
resources, reaches states, or exposes protected effects. A target adapter owns
those mechanics and supplies concrete execution context to the generic engine.
"""
from __future__ import annotations

from typing import Protocol

from core.models import Observation, Probe
from violation.counterfactual import CounterfactualContext


class TargetAdapter(Protocol):
    """Boundary between the generic algorithm and target-specific mechanics.

    Implementations may be benchmark-specific, but code under core/, inference/,
    search/, oracle/, and violation/ should depend only on this contract and the
    generic data models.
    """

    def context_for(self, baseline: Probe) -> CounterfactualContext:
        """Return concrete actor/resource/state facts for one observed baseline."""

    def execute(self, probe: Probe) -> Observation:
        """Execute one concrete request against the target."""

    def snapshot(self) -> dict:
        """Return the observable protected state used by deterministic oracles."""

    def protected_fields_for(self, baseline: Probe) -> set[str]:
        """Return target-observable fields whose change constitutes an effect."""

    def reset(self) -> None:
        """Reset target state between independent experiments when required."""
