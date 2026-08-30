from .models import Hypothesis, Probe


def discrimination_score(probe: Probe, hypotheses: list[Hypothesis], predict) -> float:
    outcomes = {predict(hypothesis, probe).signature() for hypothesis in hypotheses}
    return float(len(outcomes))


def probe_score(probe: Probe, hypotheses: list[Hypothesis], predict, alpha: float = 0.05, beta: float = 0.05) -> float:
    return discrimination_score(probe, hypotheses, predict) - alpha * probe.cost - beta * probe.risk


class ProbeSelector:
    def __init__(self, alpha: float = 0.05, beta: float = 0.05):
        self.alpha = alpha
        self.beta = beta

    def select(self, probes: list[Probe], hypotheses: list[Hypothesis], predict) -> tuple[Probe, dict[str, float]]:
        scores = {probe.id: probe_score(probe, hypotheses, predict, self.alpha, self.beta) for probe in probes}
        selected = max(probes, key=lambda probe: (scores[probe.id], probe.id))
        return selected, scores
