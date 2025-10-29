from __future__ import annotations

"""OpenAI GPT 모델을 호출하여 커밋 메시지를 생성합니다."""

import os
from typing import Final, Any, cast
from openai import OpenAI


_DEFAULT_MODEL: Final[str] = "gpt-5-mini"

# 시스템 프롬프트를 상수로 유지하여 중복을 제거합니다.
_SYSTEM_PROMPT_BASE: Final[str] = (
    "You are an expert Git commit message generator. "
    "Always use British English (en-GB) spelling and style. "
    "Explain the intent and rationale briefly. "
    "Consider the user-provided auxiliary context if present. "
    "Return only the commit message text, without labels or code fences."
)

def _build_system_prompt(*, single_line: bool, subject_max: int | None) -> str:
    max_len = subject_max or 72
    if single_line:
        return (
            f"You are an expert Git commit message generator. "
            f"Always use British English (en-GB) spelling and style. "
            f"Return a single-line imperative subject only (<= {max_len} chars). "
            f"Do not include a body, bullet points, or any rationale. Do not include any line breaks. "
            f"Consider the user-provided auxiliary context if present. "
            f"Return only the commit message text (no code fences or prefixes like 'Commit message:')."
        )
    return (
        f"You are an expert Git commit message generator. "
        f"Always use British English (en-GB) spelling and style. "
        f"Write a single-line imperative subject (<= {max_len} chars). Then include a body in this format.\n\n"
        f"Example format (do not include the --- lines in the output):\n\n"
        f"---\n\n"
        f"<Subject line>\n\n"
        f"- <detail 1>\n"
        f"- <detail 2>\n"
        f"- <detail N>\n\n"
        f"Rationale: <1-2 concise sentences explaining the intent and why>\n\n"
        f"---\n\n"
        f"Guidelines:\n"
        f"- Use '-' bullets; keep each bullet short (<= 1 line).\n"
        f"- Prefer imperative mood verbs (Add, Fix, Update, Remove, Refactor, Document, etc.).\n"
        f"- Focus on what changed and why; avoid copying diff hunks verbatim.\n"
        f"- The only allowed label is 'Rationale:'; do not add other headings or prefaces.\n"
        f"- Do not include the '---' delimiter lines, code fences, or any surrounding labels like 'Commit message:'.\n"
        f"- Do not copy or reuse any example text verbatim; produce original content based on the provided diff and context.\n"
        f"- If few details are necessary, include at least one bullet summarising the key change.\n"
        f"- Consider the user-provided auxiliary context if present.\n"
        f"Return only the commit message text in the above format (no code fences or extra labels)."
    )


def _system_message(*, single_line: bool, subject_max: int | None) -> dict[str, str]:
    """시스템 메시지 딕셔너리를 생성합니다."""
    return {"role": "system", "content": _build_system_prompt(single_line=single_line, subject_max=subject_max)}


class CommitMessageResult:
    """커밋 메시지 생성 결과와 디버그 정보를 보관합니다.

    Notes
    -----
    모든 필드는 읽기 전용 관용으로 취급하세요.
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
    """모델 이름을 결정합니다."""

    return (
        model
        or os.environ.get("GIT_COMMIT_MESSAGE_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or _DEFAULT_MODEL
    )


def _build_user_messages(
    *,
    diff: str,
    hint: str | None,
) -> tuple[str, list[dict[str, str]]]:
    """사용자 메시지를 두 개로 분리해 구성합니다.

    Returns
    -------
    tuple[str, list[dict[str, str]]]
        첫 번째 요소는 디버그 출력을 위한 결합 문자열, 두 번째 요소는
        Chat Completions API에 전달할 user 메시지 목록입니다.
    """

    hint_content: str | None = (
        f"# Auxiliary context (user-provided)\n{hint}" if hint else None
    )
    diff_content: str = f"# Changes (diff)\n{diff}"

    messages: list[dict[str, str]] = []
    if hint_content:
        messages.append({"role": "user", "content": hint_content})
    messages.append({"role": "user", "content": diff_content})

    combined_prompt: str = "\n\n".join(
        [part for part in (hint_content, diff_content) if part is not None]
    )
    return combined_prompt, messages


def generate_commit_message(
    *,
    diff: str,
    hint: str | None,
    model: str | None,
    single_line: bool = False,
    subject_max: int | None = None,
) -> str:
    """OpenAI GPT 모델을 호출하여 커밋 메시지를 생성합니다."""

    chosen_model: str = _resolve_model(model=model)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수가 필요합니다.")

    client = OpenAI(api_key=api_key)

    _combined_prompt, user_messages = _build_user_messages(diff=diff, hint=hint)

    # Chat Completions API를 사용해 한 번의 응답을 생성 (hint와 diff를 별도 user 메시지로 전송)
    all_messages: list[dict[str, str]] = [
        _system_message(single_line=single_line, subject_max=subject_max),
        *user_messages,
    ]

    resp = client.chat.completions.create(
        model=chosen_model,
        messages=cast(Any, all_messages),
    )

    text: str = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("빈 커밋 메시지가 생성되었습니다.")
    return text


def generate_commit_message_with_info(
    *,
    diff: str,
    hint: str | None,
    model: str | None,
    single_line: bool = False,
    subject_max: int | None = None,
) -> CommitMessageResult:
    """OpenAI GPT 호출 결과와 디버그 정보를 함께 반환합니다.

    Returns
    -------
    CommitMessageResult
        생성된 메시지와 토큰 사용량, 프롬프트/응답 텍스트.
    """

    chosen_model: str = _resolve_model(model=model)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수가 필요합니다.")

    client = OpenAI(api_key=api_key)
    combined_prompt, user_messages = _build_user_messages(diff=diff, hint=hint)

    all_messages = [
        _system_message(single_line=single_line, subject_max=subject_max),
        *user_messages,
    ]

    resp = client.chat.completions.create(
        model=chosen_model,
        messages=cast(Any, all_messages),
    )

    response_text: str = (resp.choices[0].message.content or "").strip()
    if not response_text:
        raise RuntimeError("빈 커밋 메시지가 생성되었습니다.")

    response_id: str | None = getattr(resp, "id", None)
    usage = getattr(resp, "usage", None)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)

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
