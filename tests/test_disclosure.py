import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Observation
from oracle import classify_disclosure, compare


def test_effective_disclosure_is_counterexample_when_policy_expected_deny():
    observation = Observation(200, {"id": "42", "Products": []}, {}, "user_b", "GET", "/rest/basket/42")
    effect = classify_disclosure(observation, "42")
    assert effect.classification == "EFFECTIVE_DISCLOSURE"
    assert compare("DENY", effect) == "COUNTEREXAMPLE"
