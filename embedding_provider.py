#!/usr/bin/env python3

from __future__ import annotations

from providers.base import EmbeddingProvider
from providers.mock_provider import MockProvider
from providers.openai_provider import OpenAIProvider


def load_provider(name: str = "mock") -> EmbeddingProvider:

    name = name.lower().strip()

    if name == "mock":
        return MockProvider()

    if name == "openai":
        return OpenAIProvider()

    raise ValueError(
        f"Unknown embedding provider: {name}"
    )
