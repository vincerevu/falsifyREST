import subprocess
from dataclasses import dataclass
from pathlib import Path

from .base import SequenceProvider
from .proxy import ProxyTraceImporter


@dataclass
class ExplorationResult:
    traces: list
    output_folder: Path
    stdout: str = ""


class EvoMasterProvider(SequenceProvider):
    """External black-box EvoMaster launcher. Import traffic via ProxyTraceImporter after the run."""

    def __init__(self, jar: str | Path, schema: str, base_url: str, output_folder: str | Path, max_time: str = "10m",
                 headers: list[str] | None = None):
        self.jar, self.schema, self.base_url = str(jar), schema, base_url
        self.output_folder, self.max_time = Path(output_folder), max_time
        self.headers = list(headers or [])

    def run(self) -> subprocess.CompletedProcess:
        self.output_folder.mkdir(parents=True, exist_ok=True)
        command = [
            "java", "-jar", self.jar, "--blackBox", "true", "--schema", self.schema,
            "--base", self.base_url, "--maxTime", self.max_time, "--outputFolder", str(self.output_folder),
        ]
        for index, header in enumerate(self.headers):
            command.extend([f"--header{index}", header])
        return subprocess.run(command, check=True, capture_output=True, text=True)

    def generate_sequences(self, target_operations=None, trace_path: str | Path | None = None):
        result = self.run()
        if trace_path is None:
            return ExplorationResult([], self.output_folder, result.stdout)
        return ExplorationResult(ProxyTraceImporter().load(trace_path), self.output_folder, result.stdout)
