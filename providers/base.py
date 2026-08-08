#!/usr/bin/env python3

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Common interface for every embedding backend."""

    name = "base"
    model = "unknown"
    dimensions = 0

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for text."""
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]
