"""Rule-first assembly point for semantic modelling, planning and feedback."""
from dataclasses import asdict

from evidence.models import Evidence
from feedback import FeedbackStore
from inference.candidate_generator import generate_candidates
from inference.ranker import priority_score
from planner import plan_experiments
from schema.models import Operation
from semantic import enrich_from_evidence, enricher_from_env, infer_semantics


def prepare_experiments(operations: list[Operation], limit: int | None = None, evidence: list[Evidence] | None = None) -> dict:
    """No network execution occurs here, except an explicitly enabled semantic enricher."""
    model = infer_semantics(operations)
    enricher = enricher_from_env()
    model.operations = [enricher.enrich(operation) for operation in model.operations]
    enrich_from_evidence(model, evidence or [])
    hypotheses = generate_candidates(model, evidence)
    feedback = FeedbackStore()
    experiments = plan_experiments(hypotheses, limit)
    return {
        "semantic_source": sorted({item.source for item in model.operations}),
        "semantic_operations": [
            {"operation": item.operation.operation_id, "resource": item.resource, "action": item.action,
             "security_concepts": sorted(item.security_concepts), "invariants": item.likely_invariants, "source": item.source,
             "family_sources": {family: sorted(sources) for family, sources in item.family_sources.items()}, "family_confidence": item.family_confidence}
            for item in model.operations
        ],
        "hypotheses": [{**asdict(item), "priority": priority_score(item, feedback.unexplored(item))} for item in hypotheses],
        "experiments": [asdict(item) for item in experiments],
    }
