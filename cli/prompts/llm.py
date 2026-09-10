from cli.prompts._common import ask_choice, ask_text
from cli.session import LLMConfig


def prompt_llm() -> LLMConfig:
    mode = ask_choice("Testing mode", [("Rule-only", "rule-only"), ("LLM prior", "llm-prior"), ("Compare both", "compare")], "rule-only")
    if mode == "rule-only":
        return LLMConfig(mode=mode)
    provider = ask_choice("LLM provider", [("Ollama", "ollama"), ("OpenAI-compatible", "openai"), ("Disabled", "disabled")], "ollama")
    if provider == "disabled":
        return LLMConfig(mode=mode)
    model = ask_text("Model", "qwen2.5:7b" if provider == "ollama" else "")
    base_url = ask_text("LLM base URL", "http://localhost:11434/v1" if provider == "ollama" else "")
    return LLMConfig(mode=mode, provider=provider, model=model, base_url=base_url)
