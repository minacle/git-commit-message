"""Shared configuration resolvers for provider/model/language selection."""

from __future__ import annotations

from os import environ
from typing import Final


DEFAULT_PROVIDER: Final[str] = "openai"
DEFAULT_MODEL_OPENAI: Final[str] = "gpt-5-mini"
DEFAULT_MODEL_GOOGLE: Final[str] = "gemini-2.5-flash"
DEFAULT_MODEL_OLLAMA: Final[str] = "gpt-oss:20b"
DEFAULT_MODEL_LLAMACPP: Final[str] = "default"
DEFAULT_LANGUAGE: Final[str] = "en-GB"


def resolve_provider_name(
    provider: str | None,
    /,
) -> str:
    chosen = provider or environ.get("GIT_COMMIT_MESSAGE_PROVIDER") or DEFAULT_PROVIDER
    return chosen.strip().lower()


def resolve_model_name(
    model: str | None,
    provider_name: str,
    /,
) -> str:
    if provider_name == "google":
        default_model = DEFAULT_MODEL_GOOGLE
        provider_model = None
    elif provider_name == "ollama":
        default_model = DEFAULT_MODEL_OLLAMA
        provider_model = environ.get("OLLAMA_MODEL")
    elif provider_name == "llamacpp":
        default_model = DEFAULT_MODEL_LLAMACPP
        provider_model = environ.get("LLAMACPP_MODEL")
    else:
        default_model = DEFAULT_MODEL_OPENAI
        provider_model = environ.get("OPENAI_MODEL")

    return model or environ.get("GIT_COMMIT_MESSAGE_MODEL") or provider_model or default_model


def resolve_language_tag(
    language: str | None,
    /,
) -> str:
    return language or environ.get("GIT_COMMIT_MESSAGE_LANGUAGE") or DEFAULT_LANGUAGE


def validate_provider_chunk_tokens(
    provider_name: str,
    chunk_tokens: int,
    /,
) -> str | None:
    if chunk_tokens < -1:
        return (
            "'--chunk-tokens' must be -1 or greater. "
            "Use -1 to disable summarisation, or 0/positive values to enable summarisation."
        )

    if provider_name == "ollama" and chunk_tokens > 0:
        return (
            "'--chunk-tokens' with values >= 1 is not supported for provider 'ollama'. "
            "Use '--chunk-tokens 0' (single summary pass) or '--chunk-tokens -1' "
            "(disable summarisation)."
        )

    return None
