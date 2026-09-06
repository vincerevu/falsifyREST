"""Deprecated compatibility entry point for semantic candidate generation."""
from semantic.models import APISemanticModel

from .candidate_generator import generate_candidates
from .hypothesis import PolicyHypothesis


def generate_rule_hypotheses(model: APISemanticModel) -> list[PolicyHypothesis]:
    """Bootstrap candidates only; policy support is added later by evidence_inducer."""
    return generate_candidates(model)
