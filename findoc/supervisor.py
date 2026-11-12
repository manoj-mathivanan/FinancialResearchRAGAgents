"""Delegate an Infosys research question to financial and transcript specialists."""

import argparse
import json
import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from openai import APIError
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from findoc.answer import DEFAULT_MODEL, Draft, answer_question
from findoc.financial_agent import FinancialAction, investigate_financials
from findoc.investigate import FollowUp, build_investigation
from findoc.research import PERIODS, ROOT, load_snapshot
from findoc.tools.transcripts import TRANSCRIPTS
from findoc.vector import LocalEmbeddings, open_store, search, vector_engine


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_end: str | None
    financial_task: str | None
    management_task: str | None


class SupervisorState(TypedDict, total=False):
    question: str
    period_hint: str | None
    assignment: Assignment
    assignment_gap: str
    financial_findings: dict
    management_findings: dict
    result: dict


PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Delegate an Infosys research question about one quarter. The financial specialist can "
     "look up reported revenue and profit attributable to owners and compute year-over-year "
     "changes. The management specialist can search the earnings-call transcript and follow "
     "up on management's statements. Give each needed specialist a focused assignment, "
     "preserving every relevant part of the user's question. Use null for an unneeded "
     "specialist and for an ambiguous reporting quarter. Use the period hint if given."),
    ("human", "Known quarters: {periods}\nPeriod hint: {period_hint}\nQuestion: {question}"),
])


def build_supervisor(supervisor, financial, management, generator):
    def assign(state):
        plan = (PROMPT | supervisor).invoke({
            "question": state["question"], "periods": ", ".join(PERIODS),
            "period_hint": state.get("period_hint") or "none",
        })
        if not isinstance(plan, Assignment):
            raise ValueError("The supervisor did not return a structured assignment.")
        update = {"assignment": plan}
        hint = state.get("period_hint")
        if hint and plan.period_end != hint:
            update["assignment_gap"] = "The supervisor did not select the requested quarter."
        elif plan.period_end not in PERIODS:
            update["assignment_gap"] = "Specify one supported Infosys reporting quarter."
        elif not any((task or "").strip() for task in (plan.financial_task, plan.management_task)):
            update["assignment_gap"] = "The specialists do not cover this question."
        return update

    def specialists(state):
        if state.get("assignment_gap"):
            return ["compose"]
        plan = state["assignment"]
        return [
            name for name, task in (("financial", plan.financial_task), ("management", plan.management_task))
            if (task or "").strip()
        ]

    def investigate_finance(state):
        plan = state["assignment"]
        return {"financial_findings": financial(plan.financial_task, plan.period_end)}

    def investigate_management(state):
        plan = state["assignment"]
        return {"management_findings": management(plan.management_task, plan.period_end)}

    def compose(state):
        finance = state.get("financial_findings", {})
        call = state.get("management_findings", {})
        gaps = [*finance.get("gaps", []), *call.get("gaps", [])]
        if state.get("assignment_gap"):
            gaps.insert(0, state["assignment_gap"])
        passages = finance.get("passages", []) + call.get("passages", [])
        plan = state["assignment"]
        result = answer_question(state["question"], plan.period_end or "", passages, generator, gaps=gaps)
        if gaps and result["status"] == "answered":
            result["status"] = "partial"
        result.update(
            assignment=plan.model_dump(), gaps=gaps,
            financial_tools=finance.get("tools", []), transcript_searches=call.get("searches", []),
        )
        return {"result": result}

    graph = StateGraph(SupervisorState)
    graph.add_node("assign", assign)
    graph.add_node("financial", investigate_finance)
    graph.add_node("management", investigate_management)
    graph.add_node("compose", compose)
    graph.add_edge(START, "assign")
    graph.add_conditional_edges("assign", specialists, ["financial", "management", "compose"])
    graph.add_edge("financial", "compose")
    graph.add_edge("management", "compose")
    graph.add_edge("compose", END)
    return graph.compile()


def live_supervisor(model_name: str, dsn: str | None):
    model = ChatOpenAI(model=model_name, timeout=30, max_retries=1, max_tokens=1000,
                       use_responses_api=True, store=False)

    def structured(schema):
        return model.with_structured_output(schema, method="json_schema", strict=True)

    financial_planner = structured(FinancialAction)
    management_planner = structured(FollowUp)

    def financial(task, period):
        return investigate_financials(task, period, financial_planner, load_snapshot)

    def management(task, period):
        if period not in TRANSCRIPTS:
            return {"gaps": [f"No transcript is configured for {period}."]}
        if not dsn:
            return {"gaps": ["Transcript search needs a connection to the vector database."]}
        embeddings = LocalEmbeddings()
        with vector_engine(dsn) as engine:
            store = open_store(engine, embeddings)
            graph = build_investigation(
                management_planner, None, lambda query, period: search(store, embeddings, query, period, limit=2)
            )
            findings = graph.invoke({"question": task, "period_end": period})
        passages = findings["passages"]
        return {
            "passages": passages,
            "searches": findings["searches"],
            "gaps": [] if passages else [f"No transcript evidence was found for {period}."],
        }

    return build_supervisor(structured(Assignment), financial, management, structured(Draft))


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--period-end", choices=PERIODS)
    parser.add_argument("--model", default=os.getenv("FINDOC_ANSWER_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()
    if not args.question.strip():
        parser.error("Enter a question.")
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY to enable the live supervisor.")

    try:
        graph = live_supervisor(args.model, os.getenv("FINDOC_DATABASE_URL"))
        result = graph.invoke({"question": args.question, "period_hint": args.period_end})["result"]
    except APIError as exc:
        parser.exit(1, f"OpenAI request failed ({type(exc).__name__}).\n")
    except (OSError, ValueError, SQLAlchemyError) as exc:
        parser.exit(1, f"Research unavailable: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
