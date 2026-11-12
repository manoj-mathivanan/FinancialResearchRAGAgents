from datetime import date
from importlib.util import find_spec
import json
from pathlib import Path
import unittest

if find_spec("langchain_openai") is None:
    raise unittest.SkipTest("Install requirements-answer.txt to test the answer path.")

from langchain_core.runnables import RunnableLambda

from findoc.answer import Claim, Draft, answer_calculation, answer_question


class AnswerTests(unittest.TestCase):
    period = "2025-12-31"
    question = "What was the reported operating margin?"
    passage = {
        "body": "The reported operating margin was 18.4%.",
        "period_end": period,
        "pdf_page": 21,
        "transcript_page": 4,
        "source_url": "https://example.test/transcript.pdf#page=21",
    }

    def test_resolves_citation_from_retrieved_passage(self):
        def generate(prompt):
            self.assertIn(self.passage["body"], prompt.to_messages()[-1].content)
            return Draft(status="answered", claims=[Claim(text="18.4%.", source_ids=["S1"])])

        result = answer_question(self.question, self.period, [self.passage], RunnableLambda(generate))
        self.assertEqual(result["sources"]["S1"]["source_url"], self.passage["source_url"])

    def test_rejects_unknown_citation(self):
        generator = RunnableLambda(
            lambda _: Draft(status="answered", claims=[Claim(text="18.4%.", source_ids=["S9"])])
        )
        with self.assertRaisesRegex(ValueError, "outside the retrieved passages"):
            answer_question(self.question, self.period, [self.passage], generator)

    def test_empty_retrieval_skips_generation(self):
        def generate(_):
            self.fail("Generation should be skipped for empty retrieval.")

        result = answer_question(self.question, self.period, [], RunnableLambda(generate))
        self.assertEqual(result["status"], "insufficient_evidence")

    def test_calculation_passes_verified_result_and_cites_both_inputs(self):
        path = Path(__file__).resolve().parents[1] / "data" / "infosys-q4-fy26.json"
        snapshot = json.loads(path.read_text(encoding="utf-8"))

        def generate(prompt):
            self.assertIn("13.38", prompt.to_messages()[-1].content)
            return Draft(status="answered", claims=[Claim(text="Revenue grew 13.38%.", source_ids=["S1"])])

        result = answer_calculation(
            "How much did revenue grow?", date(2026, 3, 31), snapshot, "revenue", RunnableLambda(generate)
        )
        self.assertEqual(result["calculation"]["percent_change"], "13.38")
        inputs = result["sources"]["S1"]["inputs"]
        self.assertEqual(inputs["prior"]["period_end"], "2025-03-31")
        self.assertEqual(inputs["current"]["period_end"], "2026-03-31")

    def test_missing_comparison_names_the_quarter_and_skips_generation(self):
        def generate(_):
            self.fail("Generation should be skipped for missing financial facts.")

        result = answer_calculation(
            "How much did revenue grow?", date(2025, 12, 31), {"facts": []},
            "revenue", RunnableLambda(generate)
        )
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIn("2024-12-31", result["reason"])
