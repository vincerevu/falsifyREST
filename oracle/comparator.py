from .effect import EffectResult


def compare(expected: str, effect: EffectResult) -> str:
    if expected == "DENY" and effect.protected_effect:
        return "COUNTEREXAMPLE"
    if expected == "DENY" and effect.classification == "DENIED":
        return "POLICY_HOLDS"
    return "INCONCLUSIVE"


def compare_prediction(prediction: str, effect: EffectResult) -> str:
    """Compare the selected hypothesis prediction with a protected-effect observation."""
    observed = "ALLOW" if effect.protected_effect else "DENY"
    if prediction == "DENY" and observed == "ALLOW":
        return "COUNTEREXAMPLE"
    if prediction == observed:
        return "POLICY_HOLDS"
    return "CONTRADICTION"
