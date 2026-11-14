"""Bounded specialist for reported facts and year-over-year comparisons."""

from datetime import date
import json
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ConfigDict

from findoc.answer import calculation_passage
from findoc.compare import MissingFactError, compare_yoy, reported_fact


MAX_TOOL_CALLS = 3


class FinancialAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["reported_fact", "compare_yoy", "stop"]
    metric: Literal["revenue", "owners-profit"] | None


PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are the financial investigator for the specified Infosys quarter. Choose one tool "
     "for the assignment. reported_fact returns a reported quarterly amount. compare_yoy "
     "returns a current and prior-year amount and their change. Supported metrics are "
     "revenue and owners-profit (profit attributable to owners). For year-over-year growth or "
     "change, call compare_yoy directly. A reported_fact result alone leaves that comparison "
     "unfinished. If the assignment asks for "
     "both metrics, gather both. Review previous tool results to decide what remains. "
     "Do not repeat a tool and metric. Use stop when enough evidence has been gathered or "
     "no remaining tool can help. Return only the tool choice."),
    ("human", "Quarter: {period}\nAssignment: {task}\nTool results: {observations}"),
])


def investigate_financials(task: str, period: str, planner, load_snapshot) -> dict:
    """Let the model choose the next action from the validated financial tool list."""
    try:
        snapshot = load_snapshot(period)
    except MissingFactError as exc:
        return {"passages": [], "tools": [], "gaps": [str(exc)]}

    end = date.fromisoformat(period)
    observations, passages, gaps = [], [], []
    attempted = set()
    for _ in range(MAX_TOOL_CALLS):
        # Previous outputs tell the planner what it has collected and what remains.
        action = (PROMPT | planner).invoke({
            "task": task, "period": period, "observations": json.dumps(observations),
        })
        if not isinstance(action, FinancialAction):
            raise ValueError("The financial investigator did not return a structured action.")
        if action.tool == "stop":
            break
        if action.metric is None:
            gaps.append("The financial investigator did not specify a metric.")
            break
        key = (action.tool, action.metric)
        if key in attempted:
            break
        attempted.add(key)
        observation = action.model_dump()
        # The chosen action runs ordinary Python against reviewed filing facts.
        try:
            if action.tool == "compare_yoy":
                calculation = compare_yoy(snapshot, action.metric, end)
                passage = calculation_passage(calculation)
            else:
                fact = reported_fact(snapshot, action.metric, end)
                details = {
                    "company": snapshot["company"], "metric": action.metric, "scope": snapshot["scope"],
                    "unit": snapshot["unit"], **fact,
                }
                passage = {
                    "body": "Reported financial fact: " + json.dumps(details),
                    "citation": {"type": "reported_fact", "input": details},
                }
            passages.append(passage)
            observation["evidence"] = passage["body"]
        except MissingFactError as exc:
            observation["gap"] = str(exc)
            gaps.append(str(exc))
        observations.append(observation)

    if not passages and not gaps:
        gaps.append("No financial evidence was collected for the assignment.")
    return {
        "passages": passages,
        "tools": [{key: value for key, value in item.items() if key != "evidence"} for item in observations],
        "gaps": gaps,
    }
