#!/usr/bin/env python3

from __future__ import annotations

from abc import ABC, abstractmethod


class VectorStore(ABC):

    name = "base"

    @abstractmethod
    def add(
        self,
        repository: str,
        relative_path: str,
        chunk_index: int,
        vector: list[float],
        model: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        vector: list[float],
        limit: int = 10,
    ) -> list[dict]:
        """Return nearest stored vectors."""
        raise NotImplementedError
