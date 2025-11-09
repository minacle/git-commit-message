from __future__ import annotations

"""Provider routing layer for commit message generation.

This module unifies the interface across OpenAI and Google Gemini backends.
"""

from typing import Literal, Optional
import os

from . import _gpt, _gemini
from ._llm_common import CommitMessageResult

Provider = Literal["openai", "google"]

_ENV_PROVIDER = "GIT_COMMIT_MESSAGE_PROVIDER"


def _infer_provider_from_model(model: str | None) -> Provider:
    if model and "gemini" in model.lower():
        return "google"
    return "openai"


def _resolve_provider(explicit: Optional[Provider], model: str | None) -> Provider:
    env_val = os.environ.get(_ENV_PROVIDER)
    if env_val in ("openai", "google"):
        return env_val  # type: ignore[return-value]
    if explicit in ("openai", "google"):
        return explicit
    return _infer_provider_from_model(model)


def generate_commit_message(
    *,
    diff: str,
    hint: str | None,
    model: str | None,
    single_line: bool = False,
    subject_max: int | None = None,
    language: str | None = None,
    provider: Optional[Provider] = None,
) -> str:
    chosen_provider = _resolve_provider(provider, model)
    if chosen_provider == "google":
        return _gemini.generate_commit_message(
            diff=diff,
            hint=hint,
            model=model,
            single_line=single_line,
            subject_max=subject_max,
            language=language,
        )
    return _gpt.generate_commit_message(
        diff=diff,
        hint=hint,
        model=model,
        single_line=single_line,
        subject_max=subject_max,
        language=language,
    )


def generate_commit_message_with_info(
    *,
    diff: str,
    hint: str | None,
    model: str | None,
    single_line: bool = False,
    subject_max: int | None = None,
    language: str | None = None,
    provider: Optional[Provider] = None,
) -> CommitMessageResult:
    chosen_provider = _resolve_provider(provider, model)
    if chosen_provider == "google":
        return _gemini.generate_commit_message_with_info(
            diff=diff,
            hint=hint,
            model=model,
            single_line=single_line,
            subject_max=subject_max,
            language=language,
        )
    return _gpt.generate_commit_message_with_info(
        diff=diff,
        hint=hint,
        model=model,
        single_line=single_line,
        subject_max=subject_max,
        language=language,
    )
