"""AI providers. POC ships the deterministic stub; the product adds Claude
via Amazon Bedrock behind the same protocol (spec §8.3) — that provider is
the only place a model SDK import will ever live (REQ-018)."""

from src.ai.providers.stub import StubProvider

__all__ = ["StubProvider"]
