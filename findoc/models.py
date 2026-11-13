"""Configure the chat model used by the web research workflows."""

import os
from typing import Literal

from langchain_openai import ChatOpenAI


Provider = Literal["openai", "groq"]
DEFAULT_MODEL = "gpt-5.6-terra"
GROQ_MODEL = "openai/gpt-oss-20b"
KEY_ENV = {"openai": "OPENAI_API_KEY", "groq": "GROQ_API_KEY"}


def chat_model(model_name: str, provider: Provider = "openai") -> ChatOpenAI:
    options = {"model": model_name, "timeout": 30, "max_retries": 1, "max_tokens": 1000}
    if provider == "groq":
        return ChatOpenAI(
            **options, api_key=os.environ[KEY_ENV[provider]],
            base_url="https://api.groq.com/openai/v1", use_responses_api=False,
            reasoning_effort="low",
        )
    return ChatOpenAI(**options, use_responses_api=True, store=False)
