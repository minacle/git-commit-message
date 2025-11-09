from __future__ import annotations

"""Common LLM utilities shared by provider-specific backends.

This module centralises prompt construction, language resolution and the
`CommitMessageResult` data container to avoid duplication across OpenAI and
Gemini implementations.
"""

import os
from typing import Final

_DEFAULT_LANGUAGE: Final[str] = "en-GB"


def build_system_prompt(*, single_line: bool, subject_max: int | None, language: str) -> str:
    """Return the instruction/system prompt used for all providers.

    Parameters
    ----------
    single_line:
        Whether only a single-line subject should be produced.
    subject_max:
        Maximum subject line length (defaults to 72 if None).
    language:
        IETF language/locale tag controlling spelling and style.
    """
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


def resolve_language(*, language: str | None) -> str:
    """Resolve target language/locale for output style."""
    return language or os.environ.get("GIT_COMMIT_MESSAGE_LANGUAGE") or _DEFAULT_LANGUAGE


def build_user_texts(*, diff: str, hint: str | None) -> tuple[str | None, str]:
    """Return user hint and diff content strings (hint may be None)."""
    hint_content: str | None = f"# Auxiliary context (user-provided)\n{hint}" if hint else None
    diff_content: str = f"# Changes (diff)\n{diff}"
    return hint_content, diff_content


def build_combined_prompt(*, diff: str, hint: str | None) -> str:
    """Compose combined prompt text for debug/logging output."""
    hint_content, diff_content = build_user_texts(diff=diff, hint=hint)
    parts = [p for p in (hint_content, diff_content) if p is not None]
    return "\n\n".join(parts)


class CommitMessageResult:
    """Data container for a generated commit message and usage metadata."""

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
