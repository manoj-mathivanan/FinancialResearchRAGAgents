"""Run the research smoke cases and check routing, known figures, and citation targets."""

import argparse
import json
import os
from pathlib import Path
import re

from dotenv import load_dotenv
from openai import APIError
from sqlalchemy.exc import SQLAlchemyError

from findoc.research import DEFAULT_MODEL, ROOT, live_workflow


def matches(actual: dict, expected: dict) -> bool:
    return isinstance(actual, dict) and all(
        matches(actual.get(key, {}), value) if isinstance(value, dict) else actual.get(key) == value
        for key, value in expected.items()
    )


def check_case(case: dict, result: dict) -> list[str]:
    route = result["route"]
    failures = []
    if not matches({**route, "uses_transcript": bool(route["transcript_query"])}, case["expected_route"]):
        failures.append("Unexpected tool or period selection.")
    if result["status"] != case["expected_status"]:
        failures.append("Unexpected answer status.")
    if "expected_gap" in case and not any(case["expected_gap"] in gap for gap in result["gaps"]):
        failures.append("Expected evidence gap was not reported.")
    if not matches(result.get("calculation", {}), case.get("expected_calculation", {})):
        failures.append("The verified calculation or its inputs differed.")
    for expected in case.get("expected_citations", []):
        if not any(
            re.search(expected["pattern"], claim["text"])
            and any(matches(result["sources"].get(label, {}), expected["source"]) for label in claim["source_ids"])
            for claim in result["claims"]
        ):
            failures.append(f"Expected claim and citation pair was missing: {expected['pattern']}")
    return failures


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "data" / "research-smoke.json")
    parser.add_argument("--model", default=os.getenv("FINDOC_ANSWER_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("FINDOC_DATABASE_URL"):
        parser.error("Set OPENAI_API_KEY and FINDOC_DATABASE_URL to run the live cases.")
    try:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))
        if not cases:
            raise ValueError("Evaluation needs at least one case.")
        graph = live_workflow(args.model, os.environ["FINDOC_DATABASE_URL"])
        outcomes = []
        for case in cases:
            state = graph.invoke({"question": case["question"]})
            result = state["result"]
            outcomes.append({
                "name": case["name"], "failures": check_case(case, result),
                "route": result["route"], "status": result["status"], "claims": result["claims"],
                "sources": result["sources"], "gaps": result["gaps"],
                "retrieved_transcript_pages": [hit["pdf_page"] for hit in state.get("passages", [])],
                "review_note": case["review_note"],
            })
    except APIError as exc:
        parser.exit(1, f"OpenAI request failed ({type(exc).__name__}).\n")
    except (OSError, ValueError, SQLAlchemyError) as exc:
        parser.exit(1, f"Evaluation unavailable: {exc}\n")
    print(json.dumps(outcomes, indent=2, ensure_ascii=False))
    if any(outcome["failures"] for outcome in outcomes):
        parser.exit(1)


if __name__ == "__main__":
    main()
