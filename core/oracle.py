from .belief import belief_resolved


def security_oracle(hypotheses, probe, observation, threshold: float = 0.8) -> str:
    if not belief_resolved(hypotheses, threshold):
        return "blind"
    best = max(hypotheses, key=lambda hypothesis: hypothesis.weight)
    expected_allowed = best.actor_capabilities.get(probe.id, False)
    action_succeeded = 200 <= observation.status < 300
    if not expected_allowed and action_succeeded:
        return "violation"
    return "benign"
