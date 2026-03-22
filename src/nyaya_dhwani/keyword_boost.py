"""Keyword boosting for IPC/BNS section references in RAG queries.

When the user mentions a specific section number (e.g. "IPC Section 413"),
semantic search alone may miss the short mapping chunks.  This module
detects section references via regex and ensures matching chunks appear
in the retrieval results.
"""

from __future__ import annotations

import re

import pandas as pd

# Patterns: "IPC Section 413", "Section 378 of IPC", "BNS 303(1)", "IPC 420", etc.
_SECTION_RE = re.compile(
    r"""
    (?:
        (?P<act1>IPC|BNS)\s+(?:Section\s+)?(?P<num1>\d+(?:\(\d+\))?)   # "IPC Section 413" or "BNS 303(1)"
      | Section\s+(?P<num2>\d+(?:\(\d+\))?)\s+(?:of\s+)?(?P<act2>IPC|BNS)  # "Section 413 of IPC"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def detect_section_references(query: str) -> list[tuple[str, str]]:
    """Extract ``(act, section_number)`` pairs from a query string.

    >>> detect_section_references("Explain IPC Section 413 and BNS 303(1)")
    [('IPC', '413'), ('BNS', '303(1)')]
    """
    refs: list[tuple[str, str]] = []
    for m in _SECTION_RE.finditer(query):
        act = (m.group("act1") or m.group("act2") or "").upper()
        num = (m.group("num1") or m.group("num2") or "").strip()
        if act and num:
            refs.append((act, num))
    return refs


def boost_with_keywords(
    query: str,
    semantic_results: pd.DataFrame,
    all_chunks: pd.DataFrame,
    k: int = 7,
    max_boost: int = 2,
) -> pd.DataFrame:
    """Merge keyword-matched chunks into semantic search results.

    1. Detect section references in *query*.
    2. Scan *all_chunks* for rows whose ``text`` mentions those sections.
    3. Insert keyword matches at the top of *semantic_results* (deduplicated).
    4. Return at most *k* rows, re-ranked.
    """
    refs = detect_section_references(query)
    if not refs or all_chunks is None or all_chunks.empty:
        return semantic_results.head(k)

    # Build regex that matches any of the detected section numbers in chunk text.
    # E.g. for ("IPC", "413"): match "IPC 413" or "IPC Section 413" in the text.
    patterns: list[str] = []
    for act, num in refs:
        escaped = re.escape(num)
        patterns.append(rf"\b{act}\s+(?:Section\s+)?{escaped}\b")
        # Also match the reverse mapping direction, e.g. "replaces IPC 413"
        patterns.append(rf"replaces\s+{act}\s+{escaped}\b")

    combined = "|".join(patterns)
    mask = all_chunks["text"].str.contains(combined, case=False, regex=True, na=False)
    keyword_hits = all_chunks[mask].head(max_boost).copy()

    if keyword_hits.empty:
        return semantic_results.head(k)

    # Deduplicate: remove keyword hits already in semantic results.
    if "chunk_id" in semantic_results.columns and "chunk_id" in keyword_hits.columns:
        existing_ids = set(semantic_results["chunk_id"].tolist())
        keyword_hits = keyword_hits[~keyword_hits["chunk_id"].isin(existing_ids)]

    if keyword_hits.empty:
        return semantic_results.head(k)

    # Add synthetic score/rank for keyword matches (higher than semantic).
    keyword_hits["score"] = 1.0
    keyword_hits["rank"] = range(len(keyword_hits))

    # Re-rank semantic results after the keyword hits.
    sem = semantic_results.copy()
    sem["rank"] = sem["rank"] + len(keyword_hits)

    merged = pd.concat([keyword_hits, sem], ignore_index=True)
    return merged.head(k).reset_index(drop=True)
