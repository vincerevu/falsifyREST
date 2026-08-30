import time

from core.models import Observation, Probe


class ToyPolicyTarget:
    """In-memory order API: only the owner should refund a PAID order, but the target intentionally fails that check."""

    def __init__(self):
        self.orders: dict[str, dict] = {}
        self.next_id = 1

    def execute(self, probe: Probe) -> Observation:
        if probe.method == "POST" and probe.path == "/orders":
            order_id = str(self.next_id)
            self.next_id += 1
            self.orders[order_id] = {"id": order_id, "owner": probe.actor, "status": "CREATED"}
            return self._observation(probe, 201, self.orders[order_id], created=[f"order:{order_id}"], after=self.orders[order_id])
        order_id = probe.path.rstrip("/").split("/")[-2] if probe.path.endswith("/pay") or probe.path.endswith("/refund") else probe.path.rstrip("/").split("/")[-1]
        order = self.orders.get(order_id)
        if not order:
            return self._observation(probe, 404, {"error": "not found"})
        before = dict(order)
        if probe.path.endswith("/pay"):
            if order["owner"] != probe.actor or order["status"] != "CREATED":
                return self._observation(probe, 403, {"error": "not allowed"}, before=before, after=order)
            order["status"] = "PAID"
            return self._observation(probe, 200, order, modified=[f"order:{order_id}"], before=before, after=order)
        if probe.path.endswith("/refund"):
            if order["status"] != "PAID":
                return self._observation(probe, 409, {"error": "invalid state"}, before=before, after=order)
            # Intentional vulnerability: the actor is not checked against order.owner.
            order["status"] = "REFUNDED"
            return self._observation(probe, 200, order, modified=[f"order:{order_id}"], before=before, after=order)
        return self._observation(probe, 404, {"error": "not found"})

    @staticmethod
    def _observation(probe, status, body, created=None, modified=None, before=None, after=None):
        order_id = body.get("id") if isinstance(body, dict) else None
        return Observation(
            status=status, body=dict(body), headers={}, actor=probe.actor, method=probe.method, endpoint=probe.path,
            extracted_ids={"resource_id": order_id} if order_id else {},
            features={"resource_type": "order", "status_field": body.get("status") if isinstance(body, dict) else None},
            timestamp=time.time(), request_body=probe.body or {}, objects_created=created or [], objects_modified=modified or [],
            state_before=dict(before or {}), state_after=dict(after or {}),
        )
