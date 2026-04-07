"""Quick smoke test for the case search pipeline.

Run:  python tests/test_case_search_live.py

Requires INDIAN_KANOON_API_TOKEN env var.
"""

import os
import sys
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

# Set token from env or inline for testing
if not os.environ.get("INDIAN_KANOON_API_TOKEN"):
    os.environ["INDIAN_KANOON_API_TOKEN"] = "56c4b332055afa06411225184ba1fdf9675d947f"

from nyaya_dhwani.case_search import (
    search_indian_kanoon,
    fetch_ik_document,
    search_precedent_cases,
    build_cases_context,
)


def test_ik_search():
    """Test Indian Kanoon search."""
    print("\n" + "=" * 60)
    print("TEST 1: Indian Kanoon Search")
    print("=" * 60)

    cases = search_indian_kanoon(
        "theft punishment BNS Section 303",
        num_results=5,
        doctype_filter="supremecourt,highcourts",
    )
    print(f"\nFound {len(cases)} cases:")
    for i, c in enumerate(cases):
        print(f"  {i+1}. {c['title']}")
        print(f"     Court: {c['court']} | Date: {c['date']}")
        print(f"     URL: {c['url']}")
    assert len(cases) > 0, "Expected at least 1 result"
    print("\n✅ PASSED")


def test_ik_doc_fetch():
    """Test fetching a full document."""
    print("\n" + "=" * 60)
    print("TEST 2: Document Fetch")
    print("=" * 60)

    text = fetch_ik_document("50613401")  # Known working doc
    print(f"\nDoc length: {len(text)} chars")
    print(f"First 200 chars: {text[:200]}...")
    assert len(text) > 100, "Expected substantial document text"
    print("\n✅ PASSED")


def test_full_pipeline():
    """Test the complete search pipeline (without LLM refinement)."""
    print("\n" + "=" * 60)
    print("TEST 3: Full Pipeline (no LLM refinement)")
    print("=" * 60)

    cases, refined = search_precedent_cases(
        "What is the punishment for murder under BNS?",
        court_filter="all",
        top_k=5,
        skip_refinement=True,  # Skip LLM since we may not have it configured
    )
    print(f"\nFound {len(cases)} cases after re-ranking:")
    for i, c in enumerate(cases):
        has_text = "full_text" in c and len(c.get("full_text", "")) > 0
        print(f"  {i+1}. {c['title']}")
        print(f"     Court: {c['court']} | Has full text: {has_text}")

    context = build_cases_context(cases)
    print(f"\nContext length: {len(context)} chars")
    print(f"Context preview:\n{context[:500]}...")

    assert len(cases) > 0, "Expected at least 1 case"
    print("\n✅ PASSED")


if __name__ == "__main__":
    test_ik_search()
    test_ik_doc_fetch()
    test_full_pipeline()
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
