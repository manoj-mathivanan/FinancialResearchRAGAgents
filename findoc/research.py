"""Route one Infosys research question to the available tools with LangGraph."""

import argparse
from datetime import date
import json
import os
from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from openai import APIError
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from findoc.answer import DEFAULT_MODEL, Draft, answer_question, calculation_passage
from findoc.models import Provider, chat_model
from findoc.compare import MissingFactError, compare_yoy
from findoc.tools.transcripts import TRANSCRIPTS
from findoc.vector import configured_embeddings, open_store, search, vector_engine


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = {
    "2024-12-31": ("infosys-q3-fy25.json",),
    "2025-03-31": ("infosys-q4-fy26.json",),
    "2025-12-31": ("infosys-q3-fy25.json", "infosys-q3-fy26.json"),
    "2026-03-31": ("infosys-q4-fy26.json",),
}
PERIODS = sorted(set(TRANSCRIPTS) | set(SNAPSHOTS))


class Route(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_end: str | None
    metric: Literal["revenue", "owners-profit"] | None
    transcript_query: str | None


class ResearchState(TypedDict, total=False):
    """One request: nodes read this state and return updates to specific fields."""

    history: list[dict]
    question: str
    period_hint: str | None
    route: Route
    routing_gap: str
    calculation: dict
    calculation_gap: str
    passages: list[dict]
    transcript_gap: str
    result: dict


ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Choose evidence tools for one Infosys quarter. The calculator supports year-over-year "
     "changes for revenue or profit attributable to owners. Transcript search supports "
     "management commentary, reported statements, and explanations. Choose both when the "
     "question asks for a supported calculation and commentary. Provide a short transcript query "
     "focused only on the commentary part, or null when transcript search is unnecessary. Use an explicit period hint "
     "when supplied. Otherwise infer the quarter end only when unambiguous. Return null for "
     "an unknown quarter or when the question requires more than one target quarter. "
     "For unrelated or unsupported requests such as stock prices, select neither tool. "
     "Use conversation history only to resolve references in the current question. The explicit "
     "period hint takes precedence. A previous quarter is the three months before the referenced "
     "quarter. If that quarter is unsupported, leave the period null without skipping to an older "
     "indexed quarter. Make a routing decision without answering the question."),
    ("human", "Known quarter ends: {periods}\nPeriod hint: {period_hint}\nConversation history: {history}\nQuestion: {question}"),
])


def build_workflow(router, generator, calculate, retrieve):
    """Build Quick research with replaceable model and tool dependencies for tests."""

    def route_question(state):
        decision = (ROUTER_PROMPT | router).invoke({
            "question": state["question"], "periods": ", ".join(PERIODS),
            "period_hint": state.get("period_hint") or "none",
            "history": json.dumps(state.get("history", [])),
        })
        if not isinstance(decision, Route):
            raise ValueError("The routing model did not return a structured decision.")
        update = {"route": decision}
        hint = state.get("period_hint")
        if hint and decision.period_end != hint:
            update["routing_gap"] = "The router did not select the requested quarter."
        elif decision.period_end not in PERIODS:
            update["routing_gap"] = "Specify one supported Infosys reporting quarter."
        elif not decision.metric and not (decision.transcript_query or "").strip():
            update["routing_gap"] = "The available tools do not cover this question."
        return update

    def next_steps(state):
        # The model proposes a route; Python decides which graph edges are valid.
        if state.get("routing_gap"):
            return ["compose"]
        decision = state["route"]
        steps = []
        if decision.metric:
            steps.append("calculator")
        if (decision.transcript_query or "").strip():
            steps.append("transcript")
        return steps

    def calculator(state):
        decision = state["route"]
        try:
            return {"calculation": calculate(decision.period_end, decision.metric)}
        except MissingFactError as exc:
            return {"calculation_gap": str(exc)}

    def transcript(state):
        period = state["route"].period_end
        if period not in TRANSCRIPTS:
            return {"transcript_gap": f"No indexed transcript is configured for {period}."}
        if retrieve is None:
            return {"transcript_gap": "Transcript search needs a connection to the vector database."}
        passages = retrieve(state["route"].transcript_query, period)
        if not passages:
            return {"transcript_gap": f"No transcript passages were found for {period}."}
        return {"passages": passages}

    def compose(state):
        decision = state["route"]
        gaps = [state[key] for key in ("routing_gap", "calculation_gap", "transcript_gap") if key in state]
        passages = list(state.get("passages", []))
        calculation = state.get("calculation")
        if calculation:
            passages.insert(0, calculation_passage(calculation))
        result = answer_question(state["question"], decision.period_end or "", passages, generator,
                                 gaps=gaps, history=state.get("history", []))
        if gaps and result["status"] == "answered":
            result["status"] = "partial"
        result.update(route=decision.model_dump(), gaps=gaps)
        if calculation:
            result["calculation"] = calculation
        return {"result": result}

    graph = StateGraph(ResearchState)
    graph.add_node("route", route_question)
    graph.add_node("calculator", calculator)
    graph.add_node("transcript", transcript)
    graph.add_node("compose", compose)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", next_steps, ["calculator", "transcript", "compose"])
    graph.add_edge("calculator", "compose")
    graph.add_edge("transcript", "compose")
    graph.add_edge("compose", END)
    return graph.compile()


def load_snapshot(period: str) -> dict:
    filenames = SNAPSHOTS.get(period)
    if filenames is None:
        raise MissingFactError(f"No financial snapshot is configured for {period}.")
    snapshots = [json.loads((ROOT / "data" / filename).read_text(encoding="utf-8")) for filename in filenames]
    snapshot = snapshots[0]
    for other in snapshots[1:]:
        for key in ("symbol", "scope", "accounting_basis", "unit"):
            if snapshot[key] != other[key]:
                raise ValueError(f"Financial snapshots differ in {key}.")
    if len(snapshots) > 1:
        # Preserve the source of every fact when merging two compatible filings.
        snapshot = {
            **snapshot,
            "snapshot_id": "+".join(item["snapshot_id"] for item in snapshots),
            "facts": [
                {**fact, "source": fact.get("source", item["source"])}
                for item in snapshots for fact in item["facts"]
            ],
        }
    return snapshot


def calculate_from_snapshot(period: str, metric: str) -> dict:
    return compare_yoy(load_snapshot(period), metric, date.fromisoformat(period))


def live_workflow(model_name: str, dsn: str | None, *, provider: Provider = "openai"):
    def retrieve(question, period):
        embeddings = configured_embeddings()
        with vector_engine(dsn) as engine:
            return search(open_store(engine, embeddings), embeddings, question, period, limit=5)

    model = chat_model(model_name, provider)
    return build_workflow(
        model.with_structured_output(Route, method="json_schema", strict=True),
        model.with_structured_output(Draft, method="json_schema", strict=True),
        calculate_from_snapshot, retrieve if dsn else None,
    )


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--period-end", choices=PERIODS, help="Use this quarter as a routing hint.")
    parser.add_argument("--model", default=os.getenv("FINDOC_ANSWER_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()
    if not args.question.strip():
        parser.error("Enter a question.")
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY to enable live routing and answers.")
    try:
        graph = live_workflow(args.model, os.getenv("FINDOC_DATABASE_URL"))
        result = graph.invoke({"question": args.question, "period_hint": args.period_end})["result"]
    except APIError as exc:
        parser.exit(1, f"OpenAI request failed ({type(exc).__name__}). Check model access and API setup.\n")
    except (OSError, ValueError, SQLAlchemyError) as exc:
        parser.exit(1, f"Research unavailable: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
