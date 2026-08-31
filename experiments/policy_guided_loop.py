"""Rule-first assembly point for semantic modelling, planning and feedback."""
from dataclasses import asdict

from feedback import FeedbackStore
from inference.ranker import priority_score
from inference.rule_generator import generate_rule_hypotheses
from planner import plan_experiments
from schema.models import Operation
from semantic import enricher_from_env, infer_semantics


def prepare_experiments(operations: list[Operation], limit: int | None = None) -> dict:
    """No network execution occurs here, except an explicitly enabled semantic enricher."""
    model = infer_semantics(operations)
    enricher = enricher_from_env()
    model.operations = [enricher.enrich(operation) for operation in model.operations]
    hypotheses = generate_rule_hypotheses(model)
    feedback = FeedbackStore()
    experiments = plan_experiments(hypotheses, limit)
    return {
        "semantic_source": sorted({item.source for item in model.operations}),
        "semantic_operations": [
            {"operation": item.operation.operation_id, "resource": item.resource, "action": item.action,
             "security_concepts": sorted(item.security_concepts), "invariants": item.likely_invariants, "source": item.source}
            for item in model.operations
        ],
        "hypotheses": [{**asdict(item), "priority": priority_score(item, feedback.unexplored(item))} for item in hypotheses],
        "experiments": [asdict(item) for item in experiments],
    }
