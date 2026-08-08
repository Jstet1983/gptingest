#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import math

from .base import EmbeddingProvider


class MockProvider(EmbeddingProvider):
    name = "mock"
    model = "mock-v1"
    dimensions = 128

    def embed(self, text: str) -> list[float]:
        values = []

        seed = hashlib.sha256(
            text.encode("utf-8", errors="ignore")
        ).digest()

        for i in range(self.dimensions):
            b = seed[i % len(seed)]
            value = (b / 127.5) - 1.0
            values.append(value)

        magnitude = math.sqrt(
            sum(x * x for x in values)
        )

        if magnitude:
            values = [
                x / magnitude
                for x in values
            ]

        return values
