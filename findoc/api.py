"""Serve the research workspace and its question endpoint."""

from functools import lru_cache
import logging
import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from openai import APIError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from findoc.models import DEFAULT_MODEL, GROQ_MODEL, KEY_ENV, Provider
from findoc.research import PERIODS, ROOT, live_workflow
from findoc.supervisor import live_supervisor
from findoc.tools.transcripts import TRANSCRIPTS


logger = logging.getLogger(__name__)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    period_end: str | None = None
    mode: Literal["quick", "team"] = "team"

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a question.")
        return value.strip()

    @field_validator("period_end")
    @classmethod
    def supported_period(cls, value: str | None) -> str | None:
        if value is not None and value not in PERIODS:
            raise ValueError("Choose a supported reporting quarter.")
        return value


@lru_cache(maxsize=4)
def workflow_for(mode: str, model: str, dsn: str | None, provider: Provider):
    factory = live_supervisor if mode == "team" else live_workflow
    return factory(model, dsn, provider=provider)


def run_question(request: Question) -> dict:
    provider = os.getenv("FINDOC_MODEL_PROVIDER", "openai")
    if provider not in ("openai", "groq"):
        raise HTTPException(503, "The server needs a supported model provider.")
    if not os.getenv(KEY_ENV[provider]):
        raise HTTPException(503, f"The server needs {KEY_ENV[provider]} before it can answer.")
    default_model = GROQ_MODEL if provider == "groq" else DEFAULT_MODEL
    model = os.getenv("FINDOC_ANSWER_MODEL", default_model)
    workflow = workflow_for(request.mode, model, os.getenv("FINDOC_DATABASE_URL"), provider)
    return workflow.invoke({"question": request.question, "period_hint": request.period_end})["result"]


def create_app(answer=run_question) -> FastAPI:
    load_dotenv(ROOT / ".env", override=False)
    app = FastAPI(title="FinDoc Research")

    @app.get("/api/config")
    def config():
        return {"periods": PERIODS, "transcript_periods": sorted(TRANSCRIPTS)}

    @app.post("/api/ask")
    def ask(request: Question):
        try:
            return answer(request)
        except (APIError, OSError, ValueError, SQLAlchemyError) as exc:
            logger.warning("Research request failed: %s", type(exc).__name__)
            raise HTTPException(502, "Research is unavailable right now. Please try again.") from exc

    dist = ROOT / "web" / "dist"
    if (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


app = create_app()
