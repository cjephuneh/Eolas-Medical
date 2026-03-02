"""
Single place for LLM client: Azure OpenAI or OpenAI. No secrets in code; all from config.
"""
from __future__ import annotations

from openai import AzureOpenAI, OpenAI

from config import (
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY,
    OPENAI_API_KEY,
)


def get_client() -> OpenAI | AzureOpenAI | None:
    """
    Return OpenAI client for Azure or OpenAI. Prefer Azure when AZURE_OPENAI_KEY is set.
    Returns None if neither is configured.
    """
    if AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT:
        return AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT.rstrip("/"),
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION or "2025-01-01-preview",
        )
    if OPENAI_API_KEY:
        return OpenAI(api_key=OPENAI_API_KEY)
    return None


def get_model_name() -> str:
    """Model/deployment name to pass to chat.completions.create."""
    if AZURE_OPENAI_KEY and AZURE_OPENAI_DEPLOYMENT:
        return AZURE_OPENAI_DEPLOYMENT
    return "gpt-4o-mini"


def has_llm() -> bool:
    """True if any LLM (Azure or OpenAI) is configured."""
    return get_client() is not None
