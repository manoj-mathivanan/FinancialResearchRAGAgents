"""Compare keyword and vector retrieval on the same expected pages."""

import json
from pathlib import Path

from findoc.baseline import keyword


def evaluate(vector_search, keyword_db: Path, cases: Path):
    results = []
    for case in json.loads(cases.read_text(encoding="utf-8")):
        question, period, expected = case["question"], case["period_end"], case["pdf_page"]
        keyword_pages = [hit["pdf_page"] for hit in keyword.search(keyword_db, question, 3, period)]
        vector_pages = [hit["pdf_page"] for hit in vector_search(question, period)]
        results.append({
            "question": question, "period_end": period, "expected_page": expected,
            "keyword_pages": keyword_pages, "vector_pages": vector_pages,
        })
    if not results:
        raise ValueError("Evaluation needs at least one case.")
    return {
        "cases": results,
        "keyword_hits_at_3": sum(row["expected_page"] in row["keyword_pages"] for row in results),
        "vector_hits_at_3": sum(row["expected_page"] in row["vector_pages"] for row in results),
        "total_cases": len(results),
    }
