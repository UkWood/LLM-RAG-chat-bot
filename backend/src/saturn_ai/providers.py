"""Interchangeable generation contract; the only implemented provider is offline fake."""
from typing import Protocol
from .domain import Claim, GenerationRequest


class LLMProvider(Protocol):
    offline: bool
    test_only: bool

    def generate(self, request: GenerationRequest) -> tuple[Claim, ...]: ...


class FakeLLMProvider:
    offline = True
    test_only = True

    def __init__(self):
        # Test instrumentation only. No application logs or persistent question history.
        self.calls: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> tuple[Claim, ...]:
        self.calls.append(request)
        return tuple(Claim(chunk.text, chunk.chunk_id) for chunk in request.evidence)
