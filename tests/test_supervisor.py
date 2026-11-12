from importlib.util import find_spec
import unittest

if any(find_spec(package) is None for package in ("langgraph", "langchain_openai")):
    raise unittest.SkipTest("Install requirements-research.txt to test delegation.")

from langchain_core.runnables import RunnableLambda

from findoc.answer import Claim, Draft
from findoc.financial_agent import FinancialAction, investigate_financials
from findoc.investigate import FollowUp, build_investigation
from findoc.research import load_snapshot
from findoc.supervisor import Assignment, build_supervisor


class SupervisorTests(unittest.TestCase):
    def test_combines_both_specialists_once(self):
        actions = iter([
            FinancialAction(tool="compare_yoy", metric="revenue"),
            FinancialAction(tool="compare_yoy", metric="owners-profit"),
            FinancialAction(tool="stop", metric=None),
        ])
        call = build_investigation(
            RunnableLambda(lambda _: FollowUp(query=None, evidence_to_find="")),
            None,
            lambda _, period: [{
                "body": "Management reported operating margin of 18.4%.",
                "pdf_page": 21, "transcript_page": 4, "period_end": period,
                "source_url": "https://example.test/transcript.pdf#page=21",
            }],
        )
        composed = []

        def generate(prompt):
            composed.append(prompt.to_messages()[-1].content)
            return Draft(status="answered", claims=[
                Claim(text="Growth and margin.", source_ids=["S1", "S2", "S3"]),
            ])

        graph = build_supervisor(
            RunnableLambda(lambda _: Assignment(
                period_end="2025-12-31", financial_task="Compare revenue and profit", management_task="Explain margin"
            )),
            lambda task, period: investigate_financials(
                task, period, RunnableLambda(lambda _: next(actions)), load_snapshot
            ),
            lambda task, period: call.invoke({"question": task, "period_end": period}),
            RunnableLambda(generate),
        )
        result = graph.invoke({"question": "How did revenue, profit, and margin change?"})["result"]
        self.assertEqual(len(composed), 1)
        self.assertIn("8.90", composed[0])
        self.assertIn("-2.23", composed[0])
        self.assertIn("18.4%", composed[0])
        self.assertEqual([item["metric"] for item in result["financial_tools"]], ["revenue", "owners-profit"])
        self.assertEqual(result["sources"]["S3"]["pdf_page"], 21)
