from evidence.models import Evidence

from .candidate_generator import generate_candidates
from .inducer import update_from_evidence
from .hypothesis import PolicyHypothesis
from semantic.models import APISemanticModel


def induce_policy_hypotheses(model: APISemanticModel, evidence: list[Evidence]) -> list[PolicyHypothesis]:
    """Public inference entry point: generic families instantiate from executions."""
    return update_from_evidence(generate_candidates(model, evidence), evidence)
