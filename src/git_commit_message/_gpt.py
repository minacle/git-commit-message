from __future__ import annotations

from openai.types.responses import ResponseInputParam

"""Generate Git commit messages by calling an OpenAI GPT model.

Migrated to use OpenAI Responses API (client.responses.create).
"""

import os
from typing import Final
from openai import OpenAI


_DEFAULT_MODEL: Final[str] = "gpt-5-mini"
_DEFAULT_LANGUAGE: Final[str] = "en-GB"

def _build_system_prompt(
    *,
    single_line: bool,
    subject_max: int | None,
    language: str,
) -> str:
    max_len = subject_max or 72
    if single_line:
        return (
            f"You are an expert Git commit message generator. "
            f"Always use '{language}' spelling and style. "
            f"Return a single-line imperative subject only (<= {max_len} chars). "
            f"Do not include a body, bullet points, or any rationale. Do not include any line breaks. "
            f"Consider the user-provided auxiliary context if present. "
            f"Return only the commit message text (no code fences or prefixes like 'Commit message:')."
        )
    return (
        f"You are an expert Git commit message generator. "
        f"Always use '{language}' spelling and style. "
        f"The subject line is mandatory: you MUST start the output with the subject as the very first non-empty line, "
        f"in imperative mood, and keep it <= {max_len} chars. Insert exactly one blank line after the subject. "
        f"Never start with bullets, headings, labels, or any other text. Then include a body in this format.\n\n"
        f"Example format (do not include the --- lines in the output):\n\n"
        f"---\n\n"
        f"<Subject line>\n\n"
        f"- <detail 1>\n"
        f"- <detail 2>\n"
        f"- <detail N>\n\n"
        f"<Rationale label translated into the target language>: <1-2 concise sentences explaining the intent and why>\n\n"
        f"---\n\n"
        f"Guidelines:\n"
        f"- The first non-empty line MUST be the subject line; include exactly one blank line after it.\n"
        f"- Never place bullets, headings, or labels before the subject line.\n"
        f"- Use '-' bullets; keep each bullet short (<= 1 line).\n"
        f"- Prefer imperative mood verbs (Add, Fix, Update, Remove, Refactor, Document, etc.).\n"
        f"- Focus on what changed and why; avoid copying diff hunks verbatim.\n"
        f"- The only allowed label is the equivalent of 'Rationale:' translated into the target language; do not add other headings or prefaces.\n"
        f"- Do not include the '---' delimiter lines, code fences, or any surrounding labels like 'Commit message:'.\n"
        f"- Do not copy or reuse any example text verbatim; produce original content based on the provided diff and context.\n"
        f"- If few details are necessary, include at least one bullet summarising the key change.\n"
        f"- If you cannot provide any body content, still output the subject line; the subject line must never be omitted.\n"
        f"- Consider the user-provided auxiliary context if present.\n"
        f"Return only the commit message text in the above format (no code fences or extra labels)."
    )


def _instructions(
    *,
    single_line: bool,
    subject_max: int | None,
    language: str,
) -> str:
    """Create the system/developer instructions string for the Responses API."""
    return _build_system_prompt(single_line=single_line, subject_max=subject_max, language=language)


class CommitMessageResult:
    """Hold the generated commit message and debugging information.

    Notes
    -----
    Treat all fields as read-only by convention.
    """

    __slots__ = (
        "message",
        "model",
        "prompt",
        "response_text",
        "response_id",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    )

    def __init__(
        self,
        /,
        *,
        message: str,
        model: str,
        prompt: str,
        response_text: str,
        response_id: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
    ) -> None:
        self.message = message
        self.model = model
        self.prompt = prompt
        self.response_text = response_text
        self.response_id = response_id
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


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

    return (
        language
        or os.environ.get("GIT_COMMIT_MESSAGE_LANGUAGE")
        or _DEFAULT_LANGUAGE
    )


def _build_responses_input(
    *,
    diff: str,
    hint: str | None,
) -> ResponseInputParam:
    """Compose Responses API input items, separating auxiliary context and diff.

    Returns
    -------
    ResponseInputParam
        The list of input items to send to the Responses API.
    """

    hint_content: str | None = (
        f"# Auxiliary context (user-provided)\n{hint}" if hint else None
    )
    diff_content: str = f"# Changes (diff)\n{diff}"

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
    hint_content: str | None = (
        f"# Auxiliary context (user-provided)\n{hint}" if hint else None
    )
    diff_content: str = f"# Changes (diff)\n{diff}"
    return "\n\n".join([part for part in (hint_content, diff_content) if part is not None])


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
