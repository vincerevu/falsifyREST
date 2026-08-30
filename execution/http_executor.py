import json
import time
import urllib.error
import urllib.request

from actors.actor import Actor
from core.models import Observation, Probe
from .session import Session


class HTTPExecutor:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def execute(self, probe: Probe, session: Session) -> Observation:
        payload = json.dumps(probe.body).encode("utf-8") if probe.body is not None else None
        request = urllib.request.Request(self.base_url + probe.path, data=payload, method=probe.method.upper(), headers=session.with_json())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.status
                headers = dict(response.headers.items())
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            status = error.code
            headers = dict(error.headers.items()) if error.headers else {}
            raw = error.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as error:
            status = 599
            headers = {}
            raw = str(error)
        try:
            body = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            body = raw
        features = {}
        if isinstance(body, dict):
            features["status_field"] = body.get("status")
        return Observation(status, body, headers, session.actor, probe.method.upper(), probe.path, features=features, timestamp=time.time())

    def execute_as(self, probe: Probe, actor: Actor) -> Observation:
        """Execute a normalized probe with an Actor's token, headers and cookies."""
        return self.execute(probe, Session(actor.id, actor.request_headers()))
