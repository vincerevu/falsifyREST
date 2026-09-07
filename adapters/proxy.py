import json
from pathlib import Path

from core.models import Observation
from execution.trace_store import Trace


class ProxyTraceImporter:
    """Import normalized JSONL traffic captured between EvoMaster and the SUT."""

    def load(self, path: str | Path) -> list[Trace]:
        trace = Trace()
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            trace.append(Observation(
                status=item["status_code"], body=item.get("response_body"), headers=item.get("response_headers", {}),
                # Some black-box generators append an identical static header more
                # than once.  The actor label is provenance metadata, so collapse
                # it deterministically before evidence uses it as an identity.
                actor=str(item.get("actor", "anonymous")).split(",", 1)[0].strip() or "anonymous",
                method=item["method"], endpoint=item["endpoint"],
                request_path=item.get("request_path", {}), request_query=item.get("request_query", {}),
                request_body=item.get("request_body", {}), extracted_ids=item.get("extracted_ids", {}),
                features=item.get("features", {}), objects_read=item.get("objects_read", []),
                objects_created=item.get("objects_created", []), objects_modified=item.get("objects_modified", []),
                state_before=item.get("state_before", {}), state_after=item.get("state_after", {}), timestamp=item.get("timestamp", 0.0),
            ))
        return [trace]
