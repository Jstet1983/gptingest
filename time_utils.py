#!/usr/bin/env python3
"""
===========================================================
GitHub → GPT Ingester
Time Utilities
Version 0.1.0
===========================================================
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now():
    """
    Return a timezone-aware UTC datetime.
    """
    return datetime.now(UTC)


def utc_iso():
    """
    Return an ISO-8601 UTC timestamp.
    Example:
        2026-08-07T22:53:02.123456+00:00
    """
    return utc_now().isoformat()


def utc_filename():
    """
    Safe timestamp for filenames.
    Example:
        20260807_225302
    """
    return utc_now().strftime("%Y%m%d_%H%M%S")
