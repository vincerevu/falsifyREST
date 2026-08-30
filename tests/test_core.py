import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.belief import belief_resolved, normalize, update_belief
from core.models import Hypothesis, Observation, Probe
from core.prediction import predict
from core.selector import discrimination_score
from adapters.evomaster_adapter import EvoMasterAdapter


def test_discrimination_prefers_state_sensitive_probe():
    hypotheses = [
        Hypothesis("draft", "draft", {"get_order": True, "approve_order": False}, weight=0.5),
        Hypothesis("submitted", "submitted", {"get_order": True, "approve_order": True}, weight=0.5),
    ]
    assert discrimination_score(Probe("approve_order", "manager", "POST", "/approve"), hypotheses, predict) == 2
    assert discrimination_score(Probe("get_order", "owner", "GET", "/order"), hypotheses, predict) == 2


def test_get_observation_resolves_phase():
    hypotheses = [
        Hypothesis("draft", "draft", {"get_order": True}, weight=0.5),
        Hypothesis("submitted", "submitted", {"get_order": True}, weight=0.5),
    ]
    update_belief(hypotheses, Probe("get_order", "owner", "GET", "/order"), Observation(200, {"status": "draft"}, {}, "owner", "GET", "/order", features={"status_field": "draft"}), predict)
    assert belief_resolved(hypotheses)
    assert max(hypotheses, key=lambda h: h.weight).phase == "draft"


def test_evomaster_adapter_normalizes_actions():
    probes = EvoMasterAdapter().convert([{"id": "approve_order", "actor": "manager", "method": "post", "path": "/order/1/approve"}])
    assert probes[0].method == "POST"
    assert probes[0].actor == "manager"
    assert probes[0].path == "/order/1/approve"
