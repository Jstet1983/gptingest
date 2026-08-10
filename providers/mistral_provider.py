#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .base import EmbeddingProvider


class MistralProvider(EmbeddingProvider):

    name = "mistral"

    def __init__(
        self,
        model: str = "mistral-embed",
        api_key: str | None = None,
    ):
        self.model = model
        self.api_key = (
            api_key or
            os.environ.get("MISTRAL_API_KEY")
        )

        if not self.api_key:
            raise RuntimeError(
                "MISTRAL_API_KEY is not set."
            )

        self.endpoint = (
            "https://api.mistral.ai/v1/embeddings"
        )

        self.dimensions = 1024

    def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        if not texts:
            return []

        payload = json.dumps({
            "model": self.model,
            "input": texts,
        }).encode("utf-8")

        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization":
                    f"Bearer {self.api_key}",
                "Content-Type":
                    "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=120,
            ) as response:
                body = json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(
                "utf-8",
                errors="replace",
            )
            raise RuntimeError(
                f"Mistral batch embedding HTTP "
                f"{exc.code}: {detail}"
            ) from exc

        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Mistral batch connection failed: "
                f"{exc}"
            ) from exc

        data = body.get("data")

        if not data:
            raise RuntimeError(
                "Mistral response contained no "
                "embedding data."
            )

        ordered = sorted(
            data,
            key=lambda item: item.get("index", 0),
        )

        vectors = [
            item["embedding"]
            for item in ordered
        ]

        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Mistral returned {len(vectors)} "
                f"embeddings for {len(texts)} inputs."
            )

        dimension = len(vectors[0])

        if any(
            len(vector) != dimension
            for vector in vectors
        ):
            raise RuntimeError(
                "Mistral returned inconsistent "
                "vector dimensions."
            )

        self.dimensions = dimension
        return vectors

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]
