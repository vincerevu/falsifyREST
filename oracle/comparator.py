from .effect import EffectResult


def compare(expected: str, effect: EffectResult) -> str:
    if expected == "DENY" and effect.protected_effect:
        return "COUNTEREXAMPLE"
    if expected == "DENY" and effect.classification == "DENIED":
        return "POLICY_HOLDS"
    return "INCONCLUSIVE"
