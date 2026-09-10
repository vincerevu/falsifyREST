from cli.prompts._common import ask_choice, ask_text
from cli.session import TargetConfig


def prompt_target() -> TargetConfig:
    base_url = ask_text("Target base URL", "http://localhost:3000").rstrip("/")
    source = ask_choice("OpenAPI source", [("Local file", "file"), ("URL", "url"), ("Auto-discover", "auto")], "file")
    openapi = ask_text("OpenAPI path or URL", f"{base_url}/openapi.json" if source != "file" else "openapi.json")
    return TargetConfig(base_url, openapi, source)
