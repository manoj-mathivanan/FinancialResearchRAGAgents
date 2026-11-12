from importlib.util import find_spec
import unittest

if any(find_spec(package) is None for package in ("langgraph", "langchain_openai")):
    raise unittest.SkipTest("Install requirements-research.txt to test investigation.")

from langchain_core.runnables import RunnableLambda

from findoc.answer import Claim, Draft
from findoc.investigate import FollowUp, build_investigation


class InvestigationTests(unittest.TestCase):
    period = "2025-12-31"

    def passage(self, page, body):
        return {
            "body": body, "pdf_page": page, "transcript_page": page - 17, "period_end": self.period,
            "source_url": f"https://example.test/transcript.pdf#page={page}",
        }

    def test_follow_up_depends_on_initial_evidence(self):
        first = self.passage(21, "Management reported operating margin of 18.4%.")
        later = self.passage(22, "Adjusted free cash flow was $965 million.")

        def plan(prompt):
            text = prompt.to_messages()[-1].content
            self.assertIn(first["body"], text)
            if later["body"] in text:
                return FollowUp(query=None, evidence_to_find="")
            return FollowUp(query="adjusted free cash flow", evidence_to_find="Management's cash-flow figure.")

        graph = build_investigation(
            RunnableLambda(plan),
            RunnableLambda(lambda _: Draft(status="answered", claims=[
                Claim(text="Management discussed margin and cash flow.", source_ids=["S1", "S2"])
            ])),
            lambda query, _: [first, later] if query == "adjusted free cash flow" else [first],
        )
        result = graph.invoke({"question": "What did management say?", "period_end": self.period})["result"]
        self.assertEqual(len(result["searches"]), 2)
        self.assertEqual(result["sources"]["S2"]["pdf_page"], 22)

    def test_stops_after_two_follow_ups(self):
        queries = iter(["first follow-up", "second follow-up"])
        graph = build_investigation(
            RunnableLambda(lambda _: FollowUp(query=next(queries), evidence_to_find="More context.")),
            RunnableLambda(lambda _: Draft(status="insufficient_evidence", claims=[])),
            lambda *_: [self.passage(21, "Some evidence.")],
        )
        result = graph.invoke({"question": "What did management say?", "period_end": self.period})["result"]
        self.assertEqual(len(result["searches"]), 3)
