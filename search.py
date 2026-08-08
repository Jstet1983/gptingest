#!/usr/bin/env python3
"""
GitHub → GPT Ingester
Vector Search CLI
Version 0.1.0
"""

from __future__ import annotations

import argparse

from embedding_provider import load_provider
from vector_store import load_vector_store


def parse_args():

    parser = argparse.ArgumentParser(
        description="Search the GPT ingestion vector store"
    )

    parser.add_argument(
        "query",
        help="Search query",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of results",
    )

    parser.add_argument(
        "--provider",
        default="mock",
        help="Embedding provider",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    if args.limit < 1:
        raise SystemExit(
            "--limit must be >= 1"
        )

    provider = load_provider(
        args.provider
    )

    store = load_vector_store(
        "sqlite"
    )

    vector = provider.embed(
        args.query
    )

    results = store.search(
        vector,
        limit=args.limit,
    )

    print()
    print("===================================")
    print("GPT Ingester Search")
    print("===================================")
    print("Query    :", args.query)
    print("Provider :", provider.name)
    print("Results  :", len(results))
    print("===================================")

    for index, result in enumerate(
        results,
        1,
    ):

        print()
        print(
            f"[{index}] "
            f"Score={result['score']:.6f}"
        )

        print(
            f"Repository: "
            f"{result['repository']}"
        )

        print(
            f"Path: "
            f"{result['relative_path']}"
        )

        print(
            f"Chunk: "
            f"{result['chunk_index']}"
        )

        print(
            f"Language: "
            f"{result['language']}"
        )

        print(
            f"MIME: "
            f"{result['mime_type']}"
        )

        text = result["text"]

        print("Text:")
        print(text[:1000])

        if len(text) > 1000:
            print("...[truncated]")

    store.close()


if __name__ == "__main__":
    main()
