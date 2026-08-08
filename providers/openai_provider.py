#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .base import EmbeddingProvider


class OpenAIProvider(EmbeddingProvider):

    name = "openai"

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
    ):

        self.model = model

        self.api_key = (
            api_key
            or os.environ.get("OPENAI_API_KEY")
        )

        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set."
            )

        self.endpoint = (
            "https://api.openai.com/v1/embeddings"
        )

        self.dimensions = 1536

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
                f"OpenAI batch embedding HTTP "
                f"{exc.code}: {detail}"
            ) from exc

        except urllib.error.URLError as exc:

            raise RuntimeError(
                f"OpenAI batch connection failed: "
                f"{exc}"
            ) from exc

        data = body.get("data")

        if not data:
            raise RuntimeError(
                "OpenAI batch response contained "
                "no embedding data."
            )

        ordered = sorted(
            data,
            key=lambda item: item.get(
                "index", 0
            ),
        )

        vectors = [
            item["embedding"]
            for item in ordered
        ]

        if len(vectors) != len(texts):
            raise RuntimeError(
                "OpenAI returned "
                f"{len(vectors)} embeddings for "
                f"{len(texts)} inputs."
            )

        self.dimensions = len(vectors[0])

        return vectors

    def embed(
        self,
        text: str,
    ) -> list[float]:

        payload = json.dumps({
            "model": self.model,
            "input": text,
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
                timeout=60,
            ) as response:

                body = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

        except urllib.error.HTTPError as exc:

            detail = exc.read().decode(
                "utf-8",
                errors="replace",
            )

            raise RuntimeError(
                f"OpenAI embedding HTTP "
                f"{exc.code}: {detail}"
            ) from exc

        except urllib.error.URLError as exc:

            raise RuntimeError(
                f"OpenAI embedding connection "
                f"failed: {exc}"
            ) from exc

        data = body.get("data")

        if not data:
            raise RuntimeError(
                "OpenAI response contained no "
                "embedding data."
            )

        vector = data[0].get("embedding")

        if not vector:
            raise RuntimeError(
                "OpenAI response contained no "
                "embedding vector."
            )

        self.dimensions = len(vector)

        return vector
