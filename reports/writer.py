import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def write_finding(path: str | Path, finding: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(finding, indent=2, default=lambda value: asdict(value) if is_dataclass(value) else str(value)), encoding="utf-8")
    return output
