from cli.prompts._common import ask_choice, ask_text
from cli.session import ExplorationConfig


def prompt_run() -> tuple[ExplorationConfig, int, str]:
    provider = ask_choice("Exploration provider", [("EvoMaster", "evomaster"), ("Existing trace", "trace"), ("Skip exploration", "skip")], "skip")
    trace = ask_text("Trace JSONL path", "") if provider == "trace" else None
    jar = ask_text("EvoMaster JAR path", "") if provider == "evomaster" else None
    budget = int(ask_text("Experiment budget", "50"))
    output = ask_text("Output directory", "output")
    return ExplorationConfig(provider, trace or None, jar or None), budget, output
