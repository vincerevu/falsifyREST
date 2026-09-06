"""Bounded semantic enrichment. LLM output is treated only as untrusted candidate metadata."""
import json
import os
import urllib.request
from abc import ABC, abstractmethod

from .models import SemanticOperation


class SemanticEnricher(ABC):
    @abstractmethod
    def enrich(self, operation: SemanticOperation) -> SemanticOperation:
        """Return metadata only; callers must keep policy validation deterministic."""


class DisabledSemanticEnricher(SemanticEnricher):
    def enrich(self, operation: SemanticOperation) -> SemanticOperation:
        return operation


class OpenAICompatibleSemanticEnricher(SemanticEnricher):
    def __init__(self, base_url: str, model: str, api_key: str | None = None, timeout: float = 20.0):
        self.base_url, self.model, self.api_key, self.timeout = base_url.rstrip("/"), model, api_key, timeout

    def enrich(self, operation: SemanticOperation) -> SemanticOperation:
        prompt = self._prompt(operation)
        request_body = {"model": self.model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [
            {"role": "system", "content": "Return only JSON. Do not propose requests, exploits, verdicts, or credentials."},
            {"role": "user", "content": prompt},
        ]}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(request_body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode())
        content = payload["choices"][0]["message"]["content"]
        return self._apply(operation, json.loads(content))

    @staticmethod
    def _prompt(operation: SemanticOperation) -> str:
        return json.dumps({
            "method": operation.operation.method, "path": operation.operation.path, "operation_id": operation.operation.operation_id,
            "task": "Return resource, action, possible_state_fields, possible_actor_relations, candidate_policy_families (ownership/state-transition/replay), and likely_invariants as JSON. These are candidates, not policy verdicts.",
        })

    @staticmethod
    def _apply(operation: SemanticOperation, result: dict) -> SemanticOperation:
        resource = str(result.get("resource", operation.resource)).lower()
        action = str(result.get("action", operation.action)).lower()
        concepts = {item for item in result.get("security_concepts", []) if item in {"ownership", "state-transition", "replay"}}
        families = {item for item in result.get("candidate_policy_families", result.get("security_concepts", [])) if item in {"ownership", "state-transition", "replay"}}
        invariants = [str(item) for item in result.get("likely_invariants", [])][:5]
        operation.resource, operation.action = resource, action
        operation.security_concepts.update(concepts)
        for family in families:
            operation.add_family(family, "llm", 0.65)
        operation.state_fields = list(dict.fromkeys([*operation.state_fields, *[str(item) for item in result.get("possible_state_fields", [])][:5]]))
        operation.relationship_fields = list(dict.fromkeys([*operation.relationship_fields, *[str(item) for item in result.get("possible_actor_relations", [])][:5]]))
        operation.likely_invariants = list(dict.fromkeys([*operation.likely_invariants, *invariants]))
        operation.confidence = max(operation.confidence, 0.65)
        if not families:
            operation.source = "+".join(sorted({*operation.source.split("+"), "llm"}))
        return operation


class OllamaSemanticEnricher(OpenAICompatibleSemanticEnricher):
    """Ollama's OpenAI-compatible endpoint; no cloud key is required."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434/v1", timeout: float = 20.0):
        super().__init__(base_url, model, None, timeout)


def enricher_from_env() -> SemanticEnricher:
    provider = os.getenv("FALSIFYREST_LLM_PROVIDER", "disabled").lower()
    if provider == "openai":
        return OpenAICompatibleSemanticEnricher(os.environ["FALSIFYREST_LLM_BASE_URL"], os.environ["FALSIFYREST_LLM_MODEL"], os.getenv("FALSIFYREST_LLM_API_KEY"))
    if provider == "ollama":
        return OllamaSemanticEnricher(os.environ["FALSIFYREST_LLM_MODEL"], os.getenv("FALSIFYREST_LLM_BASE_URL", "http://localhost:11434/v1"))
    return DisabledSemanticEnricher()
