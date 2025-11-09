from __future__ import annotations

from openai.types.responses import ResponseInputParam

"""Generate Git commit messages by calling an OpenAI GPT model.

Migrated to use OpenAI Responses API (client.responses.create).
"""

import os
from typing import Final
from openai import OpenAI

from ._llm_common import (
    build_system_prompt,
    resolve_language,
    build_user_texts,
    build_combined_prompt,
    CommitMessageResult,
)

_DEFAULT_MODEL: Final[str] = "gpt-5-mini"


def _instructions(
    *,
    single_line: bool,
    subject_max: int | None,
    language: str,
) -> str:
    """Create the system/developer instructions string for the Responses API."""
    return build_system_prompt(single_line=single_line, subject_max=subject_max, language=language)


# Re-export CommitMessageResult directly from common module (no subclass needed)


def _resolve_model(
    *,
    model: str | None,
) -> str:
    """Resolve the model name."""

    return (
        model
        or os.environ.get("GIT_COMMIT_MESSAGE_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or _DEFAULT_MODEL
    )


def _resolve_language(
    *,
    language: str | None,
) -> str:
    """Resolve the target language/locale tag used for output style."""
    return resolve_language(language=language)


def _build_responses_input(
    *,
    diff: str,
    hint: str | None,
) -> ResponseInputParam:
    """Compose Responses API input items, separating auxiliary context and diff."""
    hint_content, diff_content = build_user_texts(diff=diff, hint=hint)
    input_items: ResponseInputParam = []
    if hint_content:
        input_items.append(
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": hint_content},
                ],
            }
        )
    input_items.append(
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": diff_content},
            ],
        }
    )
    return input_items


def _build_combined_prompt(*, diff: str, hint: str | None) -> str:
    """Compose a combined string of hint and diff for debug/info output."""
    return build_combined_prompt(diff=diff, hint=hint)


def generate_commit_message(
    *,
    diff: str,
    hint: str | None,
    model: str | None,
    single_line: bool = False,
    subject_max: int | None = None,
    language: str | None = None,
) -> str:
    """Generate a commit message using an OpenAI GPT model."""

    chosen_model: str = _resolve_model(model=model)
    chosen_language: str = _resolve_language(language=language)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("The OPENAI_API_KEY environment variable is required.")

    client = OpenAI(api_key=api_key)

    input_items = _build_responses_input(diff=diff, hint=hint)

    # Use Responses API to generate a single response (send hint and diff as separate user inputs)
    resp = client.responses.create(
        model=chosen_model,
        instructions=_instructions(single_line=single_line, subject_max=subject_max, language=chosen_language),
        input=input_items,
    )

    # Prefer SDK convenience aggregate text if available
    text: str = (resp.output_text or "").strip()
    if not text:
        raise RuntimeError("An empty commit message was generated.")
    return text


def generate_commit_message_with_info(
    *,
    diff: str,
    hint: str | None,
    model: str | None,
    single_line: bool = False,
    subject_max: int | None = None,
    language: str | None = None,
) -> CommitMessageResult:
    """Return the OpenAI GPT call result together with debugging information.

    Returns
    -------
    CommitMessageResult
        The generated message, token usage, and prompt/response text.
    """

    chosen_model: str = _resolve_model(model=model)
    chosen_language: str = _resolve_language(language=language)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("The OPENAI_API_KEY environment variable is required.")

    client = OpenAI(api_key=api_key)
    combined_prompt = _build_combined_prompt(diff=diff, hint=hint)
    input_items = _build_responses_input(diff=diff, hint=hint)

    resp = client.responses.create(
        model=chosen_model,
        instructions=_instructions(single_line=single_line, subject_max=subject_max, language=chosen_language),
        input=input_items,
    )

    response_text: str = (resp.output_text or "").strip()
    if not response_text:
        raise RuntimeError("An empty commit message was generated.")

    response_id: str | None = resp.id
    usage = resp.usage
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    if usage is not None:
        # Responses API exposes input/output/total token fields.
        total_tokens = usage.total_tokens
        prompt_tokens = usage.input_tokens
        completion_tokens = usage.output_tokens

    return CommitMessageResult(
        message=response_text,
        model=chosen_model,
        prompt=combined_prompt,
        response_text=response_text,
        response_id=response_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
