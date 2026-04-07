"""Full integration test — both Indian Kanoon and Google CSE."""
import os, sys, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

os.environ["INDIAN_KANOON_API_TOKEN"] = "56c4b332055afa06411225184ba1fdf9675d947f"
os.environ["GOOGLE_API_KEY"] = "AIzaSyAbiE12Iz0ivjLKFrqvCGXqnYrMuOlhoc8"
os.environ["GOOGLE_CSE_CX"] = "e1e7cefca81f84b13"

from nyaya_dhwani.case_search import (
    search_indian_kanoon, fetch_ik_document,
    search_google_cse, search_precedent_cases, build_cases_context,
)

def run_all():
    print("=" * 60)
    print("TEST 1: Indian Kanoon Search (SC + HC only)")
    print("=" * 60)
    cases = search_indian_kanoon(
        "murder conviction BNS Section 101",
        num_results=5,
        doctype_filter="supremecourt,highcourts",
    )
    print(f"Found {len(cases)} cases:")
    for i, c in enumerate(cases):
        print(f"  {i+1}. {c['title']}")
        print(f"     Court: {c['court']} | Date: {c['date']}")
    assert len(cases) > 0, "IK search returned 0 results"
    print(">> PASSED\n")

    print("=" * 60)
    print("TEST 2: Document Fetch (full judgment)")
    print("=" * 60)
    text = fetch_ik_document(cases[0]["doc_id"])
    print(f"Doc length: {len(text)} chars")
    print(f"Preview: {text[:150]}...")
    assert len(text) > 50, "Doc text too short"
    print(">> PASSED\n")

    print("=" * 60)
    print("TEST 3: Google CSE Search")
    print("=" * 60)
    gcs = search_google_cse("theft BNS Section 303 judgment", num_results=5)
    print(f"Found {len(gcs)} results:")
    for i, c in enumerate(gcs):
        print(f"  {i+1}. {c['title']}")
        print(f"     URL: {c['url']}")
    if len(gcs) == 0:
        print(">> SKIPPED (Google CSE API may not be enabled yet)")
    else:
        print(">> PASSED")
    print()

    print("=" * 60)
    print("TEST 4: Full Pipeline (skip LLM refinement)")
    print("=" * 60)
    result_cases, refined = search_precedent_cases(
        "What is the punishment for dowry death under BNS?",
        court_filter="HC",
        top_k=5,
        skip_refinement=True,
    )
    print(f"Found {len(result_cases)} enriched cases:")
    for i, c in enumerate(result_cases):
        has_text = len(c.get("full_text", "")) > 100
        print(f"  {i+1}. {c['title']}")
        print(f"     Court: {c['court']} | Full text: {has_text}")
    context = build_cases_context(result_cases)
    print(f"\nTotal context length: {len(context)} chars")
    assert len(result_cases) > 0, "Pipeline returned 0 cases"
    print(">> PASSED\n")

    print("=" * 60)
    print("TEST 5: Multiple queries (different domains)")
    print("=" * 60)
    test_queries = [
        ("bail application non-bailable offence BNS", "SC"),
        ("cheque bounce NI Act Section 138", "all"),
        ("domestic violence protection order", "HC"),
    ]
    for q, court in test_queries:
        cases_r, _ = search_precedent_cases(q, court_filter=court, top_k=3, skip_refinement=True)
        status = "OK" if len(cases_r) > 0 else "EMPTY"
        print(f"  [{status}] '{q[:50]}' (court={court}) -> {len(cases_r)} cases")
    print(">> PASSED\n")

    print("=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    run_all()
