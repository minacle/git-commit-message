"""LLM orchestration and provider selection.

This module contains provider-agnostic logic:
- Prompt construction
- Diff chunking + summarisation flow
- Provider selection (CLI arg + env fallback)

Provider-specific API calls live in provider modules (e.g. `_gpt.py`).
"""

from __future__ import annotations

from babel import Locale
from os import environ
from typing import ClassVar, Final, Protocol


_DEFAULT_PROVIDER: Final[str] = "openai"
_DEFAULT_MODEL_OPENAI: Final[str] = "gpt-5-mini"
_DEFAULT_MODEL_GOOGLE: Final[str] = "gemini-2.5-flash"
_DEFAULT_MODEL_OLLAMA: Final[str] = "gpt-oss:20b"
_DEFAULT_MODEL_LLAMACPP: Final[str] = "default"
_DEFAULT_LANGUAGE: Final[str] = "en-GB"


class UnsupportedProviderError(RuntimeError):
    __slots__ = ()

    pass


class LLMUsage:
    __slots__ = (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    )

    def __init__(
        self,
        /,
        *,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class LLMTextResult:
    __slots__ = (
        "text",
        "response_id",
        "usage",
    )

    def __init__(
        self,
        /,
        *,
        text: str,
        response_id: str | None,
        usage: LLMUsage | None,
    ) -> None:
        self.text = text
        self.response_id = response_id
        self.usage = usage


class CommitMessageProvider(Protocol):
    __slots__ = ()

    name: ClassVar[str]

    def generate_text(
        self,
        /,
        *,
        model: str,
        instructions: str,
        user_text: str,
    ) -> LLMTextResult: ...

    def count_tokens(
        self,
        /,
        *,
        model: str,
        text: str,
    ) -> int: ...


class CommitMessageResult:
    """Hold the generated commit message and debugging information.

    Notes
    -----
    Treat all fields as read-only by convention.
    """

    __slots__ = (
        "message",
        "provider",
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
        provider: str,
        model: str,
        prompt: str,
        response_text: str,
        response_id: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
    ) -> None:
        self.message = message
        self.provider = provider
        self.model = model
        self.prompt = prompt
        self.response_text = response_text
        self.response_id = response_id
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


def _resolve_provider(
    provider: str | None,
    /,
) -> str:
    chosen = provider or environ.get("GIT_COMMIT_MESSAGE_PROVIDER") or _DEFAULT_PROVIDER
    return chosen.strip().lower()


def _resolve_model(
    model: str | None,
    provider_name: str,
    /,
) -> str:
    if provider_name == "google":
        default_model = _DEFAULT_MODEL_GOOGLE
        provider_model = None
    elif provider_name == "ollama":
        default_model = _DEFAULT_MODEL_OLLAMA
        provider_model = environ.get("OLLAMA_MODEL")
    elif provider_name == "llamacpp":
        default_model = _DEFAULT_MODEL_LLAMACPP
        provider_model = environ.get("LLAMACPP_MODEL")
    else:
        default_model = _DEFAULT_MODEL_OPENAI
        provider_model = environ.get("OPENAI_MODEL")

    return model or environ.get("GIT_COMMIT_MESSAGE_MODEL") or provider_model or default_model


def _resolve_language(
    language: str | None,
    /,
) -> str:
    return language or environ.get("GIT_COMMIT_MESSAGE_LANGUAGE") or _DEFAULT_LANGUAGE


def get_provider(
    provider: str | None,
    /,
    *,
    host: str | None = None,
) -> CommitMessageProvider:
    name = _resolve_provider(provider)

    if name == "openai":
        # Local import to avoid import cycles: providers may import shared types from this module.
        from ._gpt import OpenAIResponsesProvider

        return OpenAIResponsesProvider()

    if name == "google":
        # Local import to avoid import cycles: providers may import shared types from this module.
        from ._gemini import GoogleGenAIProvider

        return GoogleGenAIProvider()

    if name == "ollama":
        # Local import to avoid import cycles: providers may import shared types from this module.
        from ._ollama import OllamaProvider

        return OllamaProvider(host=host)

    if name == "llamacpp":
        # Local import to avoid import cycles: providers may import shared types from this module.
        from ._llamacpp import LlamaCppProvider

        return LlamaCppProvider(host=host)

    raise UnsupportedProviderError(
        f"Unsupported provider: {name}. Supported providers: openai, google, ollama, llamacpp"
    )


def _language_display(
    language: str,
    /,
) -> str:
    """Return a human-friendly language display like 'Korean (South Korea) [ko-KR]'."""

    try:
        locale = Locale.parse(language, sep="-")
    except Exception:
        return language

    tag_parts = [
        locale.language,
        locale.script,
        locale.territory,
        locale.variant,
    ]
    tag = "-".join(part for part in tag_parts if part)
    if not tag:
        return language

    english_name = locale.get_display_name("en") or ""
    if not english_name:
        return f"[{tag}]"

    return f"{english_name.capitalize()} [{tag}]"


def _build_system_prompt(
    single_line: bool,
    subject_max: int | None,
    language: str,
    /,
) -> str:
    display_language: str = _language_display(language)
    max_len = subject_max or 72
    if single_line:
        return (
            f"You are an expert Git commit message generator. "
            f"Always use '{display_language}' spelling and style. "
            f"Return a single-line imperative subject only (<= {max_len} chars). "
            f"Do not include a body, bullet points, or any rationale. Do not include any line breaks. "
            f"Consider the user-provided auxiliary context if present. "
            f"Return only the commit message text (no code fences or prefixes like 'Commit message:')."
        )
    return (
        f"You are an expert Git commit message generator. "
        f"Always use '{display_language}' spelling and style. "
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
        f"- All text (subject, bullets, rationale label, rationale content) MUST be in the target language: '{display_language}'. Do not mix other languages.\n"
        f"- Do not include the '---' delimiter lines, code fences, or any surrounding labels like 'Commit message:'.\n"
        f"- Do not copy or reuse any example text verbatim; produce original content based on the provided diff and context.\n"
        f"- If few details are necessary, include at least one bullet summarising the key change.\n"
        f"- If you cannot provide any body content, still output the subject line; the subject line must never be omitted.\n"
        f"- Consider the user-provided auxiliary context if present.\n"
        f"Return only the commit message text in the above format (no code fences or extra labels)."
    )


def _build_chunk_summary_prompt() -> str:
    return (
        "You are an expert developer summarising Git diffs. "
        "Write detailed English bullet points describing what changed and why. "
        "Do not copy large code blocks verbatim; focus on behavior and intent. "
        "Be verbose when useful; this summary will later be used to craft a commit message."
    )


def _build_combined_prompt(
    diff: str,
    hint: str | None,
    content_label: str = "Changes (diff)",
    /,
) -> str:
    hint_content: str | None = (
        f"# Auxiliary context (user-provided)\n{hint}" if hint else None
    )
    content: str = f"# {content_label}\n{diff}"
    return "\n\n".join([part for part in (hint_content, content) if part is not None])


def _split_diff_into_hunks(
    diff: str,
    /,
) -> list[str]:
    lines = diff.splitlines(keepends=True)
    hunks: list[str] = []
    file_header: list[str] = []
    current_hunk: list[str] | None = None

    for line in lines:
        if line.startswith("diff --git "):
            if current_hunk:
                hunks.append("".join(current_hunk))
                current_hunk = None
            file_header = [line]
            continue

        if line.startswith("@@"):
            if current_hunk:
                hunks.append("".join(current_hunk))
            base_header = file_header[:] if file_header else []
            current_hunk = base_header + [line]
            continue

        if current_hunk is not None:
            current_hunk.append(line)
            continue

        if file_header:
            file_header.append(line)
            continue

        current_hunk = [line]

    if current_hunk:
        hunks.append("".join(current_hunk))

    return hunks


def _build_diff_chunks(
    hunks: list[str],
    chunk_tokens: int,
    provider: CommitMessageProvider,
    model: str,
    /,
) -> list[str]:
    if chunk_tokens <= 0:
        raise ValueError("chunk_tokens must be positive when chunking is enabled")

    chunks: list[str] = []
    current: list[str] = []

    for hunk in hunks:
        candidate = "".join(current + [hunk])
        token_count = provider.count_tokens(model=model, text=candidate)

        if token_count <= chunk_tokens:
            current.append(hunk)
            continue

        if current:
            chunks.append("".join(current))
            current = [hunk]
        else:
            single_tokens = provider.count_tokens(model=model, text=hunk)
            if single_tokens > chunk_tokens:
                raise ValueError(
                    "chunk_tokens is too small to fit a single diff hunk; increase the value or disable chunking"
                )
            current = [hunk]

    if current:
        chunks.append("".join(current))

    return chunks


def _summarise_diff_chunks(
    chunks: list[str],
    provider: CommitMessageProvider,
    model: str,
    /,
) -> list[LLMTextResult]:
    if not chunks:
        return []

    instructions = _build_chunk_summary_prompt()
    results: list[LLMTextResult] = []

    for chunk in chunks:
        res = provider.generate_text(
            model=model,
            instructions=instructions,
            user_text=f"# Diff chunk\n{chunk}",
        )
        text = (res.text or "").strip()
        if not text:
            raise RuntimeError("An empty chunk summary was generated.")
        results.append(res)

    return results


def _generate_commit_from_summaries(
    summaries: list[str],
    hint: str | None,
    provider: CommitMessageProvider,
    model: str,
    single_line: bool,
    subject_max: int | None,
    language: str,
    /,
) -> LLMTextResult:
    instructions = _build_system_prompt(single_line, subject_max, language)
    sections: list[str] = []

    if hint:
        sections.append(f"# Auxiliary context (user-provided)\n{hint}")

    if summaries:
        numbered = [
            f"Summary {idx + 1}:\n{summary}" for idx, summary in enumerate(summaries)
        ]
        sections.append(
            "# Combined summaries of the commit (in English)\n" + "\n\n".join(numbered)
        )
    else:
        sections.append("# No summaries available")

    user_text = "\n\n".join(sections)

    res = provider.generate_text(
        model=model,
        instructions=instructions,
        user_text=user_text,
    )

    text = (res.text or "").strip()
    if not text:
        raise RuntimeError("An empty commit message was generated from summaries.")

    return res


def _sum_usage(
    results: list[LLMTextResult],
    /,
) -> tuple[int | None, int | None, int | None]:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    for res in results:
        usage = res.usage
        if usage is None:
            continue

        if usage.total_tokens is not None:
            total_tokens = (total_tokens or 0) + usage.total_tokens
        if usage.prompt_tokens is not None:
            prompt_tokens = (prompt_tokens or 0) + usage.prompt_tokens
        if usage.completion_tokens is not None:
            completion_tokens = (completion_tokens or 0) + usage.completion_tokens

    return prompt_tokens, completion_tokens, total_tokens


def generate_commit_message(
    diff: str,
    hint: str | None,
    model: str | None,
    single_line: bool = False,
    subject_max: int | None = None,
    language: str | None = None,
    chunk_tokens: int | None = 0,
    provider: str | None = None,
    host: str | None = None,
    /,
) -> str:
    chosen_provider = _resolve_provider(provider)
    chosen_model = _resolve_model(model, chosen_provider)
    chosen_language = _resolve_language(language)

    llm = get_provider(chosen_provider, host=host)

    normalized_chunk_tokens = 0 if chunk_tokens is None else chunk_tokens

    if normalized_chunk_tokens != -1:
        hunks = _split_diff_into_hunks(diff)
        if normalized_chunk_tokens == 0 or normalized_chunk_tokens < 0:
            chunks = ["".join(hunks) if hunks else diff]
        else:
            chunks = _build_diff_chunks(hunks, normalized_chunk_tokens, llm, chosen_model)

        summary_results = _summarise_diff_chunks(chunks, llm, chosen_model)
        summaries = [r.text for r in summary_results]
        final = _generate_commit_from_summaries(
            summaries,
            hint,
            llm,
            chosen_model,
            single_line,
            subject_max,
            chosen_language,
        )
        text = (final.text or "").strip()
    else:
        instructions = _build_system_prompt(single_line, subject_max, chosen_language)
        user_text = _build_combined_prompt(diff, hint)
        final = llm.generate_text(
            model=chosen_model,
            instructions=instructions,
            user_text=user_text,
        )
        text = (final.text or "").strip()

    if not text:
        raise RuntimeError("An empty commit message was generated.")

    return text


def generate_commit_message_with_info(
    diff: str,
    hint: str | None,
    model: str | None,
    single_line: bool = False,
    subject_max: int | None = None,
    language: str | None = None,
    chunk_tokens: int | None = 0,
    provider: str | None = None,
    host: str | None = None,
    /,
) -> CommitMessageResult:
    chosen_provider = _resolve_provider(provider)
    chosen_model = _resolve_model(model, chosen_provider)
    chosen_language = _resolve_language(language)

    llm = get_provider(chosen_provider, host=host)

    normalized_chunk_tokens = 0 if chunk_tokens is None else chunk_tokens

    response_id: str | None = None

    if normalized_chunk_tokens != -1:
        hunks = _split_diff_into_hunks(diff)
        if normalized_chunk_tokens == 0 or normalized_chunk_tokens < 0:
            chunks = ["".join(hunks) if hunks else diff]
        else:
            chunks = _build_diff_chunks(hunks, normalized_chunk_tokens, llm, chosen_model)

        summary_results = _summarise_diff_chunks(chunks, llm, chosen_model)
        summary_texts = [r.text for r in summary_results]
        final_result = _generate_commit_from_summaries(
            summary_texts,
            hint,
            llm,
            chosen_model,
            single_line,
            subject_max,
            chosen_language,
        )

        combined_prompt = _build_combined_prompt(
            "\n".join(summary_texts),
            hint,
            "Combined summaries (English)",
        )

        prompt_tokens, completion_tokens, total_tokens = _sum_usage(
            [*summary_results, final_result]
        )

        response_text = (final_result.text or "").strip()
        response_id = final_result.response_id

    else:
        instructions = _build_system_prompt(single_line, subject_max, chosen_language)
        combined_prompt = _build_combined_prompt(diff, hint)

        final_result = llm.generate_text(
            model=chosen_model,
            instructions=instructions,
            user_text=combined_prompt,
        )

        response_text = (final_result.text or "").strip()
        response_id = final_result.response_id
        if final_result.usage is None:
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
        else:
            prompt_tokens = final_result.usage.prompt_tokens
            completion_tokens = final_result.usage.completion_tokens
            total_tokens = final_result.usage.total_tokens

    if not response_text:
        raise RuntimeError("An empty commit message was generated.")

    return CommitMessageResult(
        message=response_text,
        provider=llm.name,
        model=chosen_model,
        prompt=combined_prompt,
        response_text=response_text,
        response_id=response_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
