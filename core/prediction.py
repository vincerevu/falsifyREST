from .models import Hypothesis, Prediction, Probe


def predict(hypothesis: Hypothesis, probe: Probe) -> Prediction:
    capability = hypothesis.actor_capabilities.get(probe.id, False)
    if probe.id == "get_order":
        return Prediction(200, f"phase:{hypothesis.phase}", True)
    if probe.id == "submit_order":
        if hypothesis.phase == "draft" and capability:
            return Prediction(200, "draft_to_submitted", True)
        return Prediction(409, capability_allowed=False)
    if probe.id == "approve_order":
        if hypothesis.phase == "submitted" and capability:
            return Prediction(200, "submitted_to_approved", True)
        if hypothesis.phase == "draft" and capability:
            return Prediction(200, "draft_to_approved", True)
        return Prediction(403 if hypothesis.phase == "draft" else 409, capability_allowed=False)
    return Prediction(404, capability_allowed=False)
