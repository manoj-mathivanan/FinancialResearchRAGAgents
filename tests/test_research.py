from importlib.util import find_spec
import unittest

if any(find_spec(package) is None for package in ("langgraph", "langchain_openai")):
    raise unittest.SkipTest("Install requirements-research.txt to test agent routing.")

from langchain_core.runnables import RunnableLambda

from findoc.answer import Claim, Draft
from findoc.compare import MissingFactError
from findoc.research import Route, build_workflow, calculate_from_snapshot


class ResearchTests(unittest.TestCase):
    def test_follow_up_passes_history_to_router_and_answer(self):
        history = [{"question": "How did revenue grow?", "answer": "8.90% growth.", "period_end": "2025-12-31"}]

        def route(prompt):
            self.assertIn("8.90% growth.", prompt.to_messages()[-1].content)
            return Route(period_end="2025-12-31", metric="owners-profit", transcript_query=None)

        def generate(prompt):
            message = prompt.to_messages()[-1].content
            self.assertIn("8.90% growth.", message)
            self.assertIn("6654", message)
            return Draft(status="answered", claims=[Claim(text="Profit declined.", source_ids=["S1"])])

        graph = build_workflow(RunnableLambda(route), RunnableLambda(generate),
                               calculate_from_snapshot, self.unexpected_call)
        result = graph.invoke({"question": "What about profit?", "history": history})["result"]
        self.assertEqual(result["calculation"]["metric"], "owners-profit")
        self.assertEqual(result["sources"]["S1"]["inputs"]["current"]["value"], "6654")

    def run_route(self, decision, *, calculate, retrieve, generate, period_hint=None):
        graph = build_workflow(
            RunnableLambda(lambda _: decision), RunnableLambda(generate), calculate, retrieve
        )
        return graph.invoke({"question": "Infosys question", "period_hint": period_hint})["result"]

    def unexpected_call(self, *_):
        self.fail("The router did not select this step.")

    def test_calculator_route_needs_no_retrieval(self):
        result = self.run_route(
            Route(period_end="2026-03-31", metric="revenue", transcript_query=None),
            calculate=calculate_from_snapshot, retrieve=self.unexpected_call,
            generate=lambda _: Draft(status="answered", claims=[Claim(text="13.38%.", source_ids=["S1"])]),
        )
        self.assertEqual(result["calculation"]["percent_change"], "13.38")

    def test_both_tools_compose_once_and_report_missing_calculation(self):
        calls = []

        def calculate(period, metric):
            raise MissingFactError("Missing 2024-12-31 in this test snapshot.")

        def retrieve(question, period):
            self.assertEqual(question, "operating margin")
            calls.append("search")
            return [{
                "body": "Management described operating margin.",
                "source_url": "https://example.test/transcript.pdf#page=21",
                "pdf_page": 21, "transcript_page": 4, "period_end": period,
            }]

        def generate(prompt):
            calls.append("answer")
            self.assertIn("2024-12-31", prompt.to_messages()[-1].content)
            return Draft(status="answered", claims=[Claim(text="Margin commentary.", source_ids=["S1"])])

        result = self.run_route(
            Route(period_end="2025-12-31", metric="revenue", transcript_query="operating margin"),
            calculate=calculate, retrieve=retrieve, generate=generate,
        )
        self.assertEqual(calls, ["search", "answer"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["sources"]["S1"]["pdf_page"], 21)

    def test_december_comparison_preserves_each_filings_source(self):
        result = calculate_from_snapshot("2025-12-31", "revenue")
        self.assertEqual(result["percent_change"], "8.90")
        self.assertEqual(result["prior"]["value"], "41764")
        self.assertEqual(result["current"]["value"], "45479")
        self.assertTrue(result["prior"]["source"]["url"].endswith("January162025.pdf#page=80"))
        self.assertTrue(result["current"]["source"]["url"].endswith("January142026.pdf#page=87"))

    def test_rejects_route_that_conflicts_with_explicit_period(self):
        result = self.run_route(
            Route(period_end="2024-12-31", metric=None, transcript_query="operating margin"),
            calculate=self.unexpected_call, retrieve=self.unexpected_call, generate=self.unexpected_call,
            period_hint="2025-12-31",
        )
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIn("requested quarter", result["gaps"][0])
