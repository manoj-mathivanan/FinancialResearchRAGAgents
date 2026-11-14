from importlib.util import find_spec
import unittest

if any(find_spec(package) is None for package in ("fastapi", "langgraph", "langchain_openai")):
    raise unittest.SkipTest("Install requirements-web.txt to test the API.")

from fastapi.testclient import TestClient

from findoc.api import create_app


class ResearchAPITests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def answer(request):
            self.calls.append(request)
            return {
                "status": "partial", "claims": [{"text": "Revenue grew.", "source_ids": ["S1"]}],
                "sources": {"S1": {"source_url": "https://example.test/call.pdf#page=21"}},
                "gaps": ["No corroborating filing was supplied."],
            }

        self.client = TestClient(create_app(answer))
        self.addCleanup(self.client.close)

    def test_passes_question_and_preserves_sources_and_gaps(self):
        response = self.client.post("/api/ask", json={
            "question": "  How did revenue change? ", "period_end": "2025-12-31", "mode": "team",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls[0].question, "How did revenue change?")
        self.assertEqual(self.calls[0].mode, "team")
        self.assertEqual(self.calls[0].symbol, "INFY")
        self.assertIn("S1", response.json()["sources"])
        self.assertEqual(response.json()["status"], "partial")

    def test_rejects_unknown_quarter_before_running_workflow(self):
        response = self.client.post("/api/ask", json={"question": "Revenue?", "period_end": "2023-03-31"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.calls, [])

    def test_rejects_unknown_stock_before_running_workflow(self):
        response = self.client.post("/api/ask", json={"question": "Revenue?", "symbol": "OTHER"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.calls, [])
