from __future__ import annotations

"""OpenAI GPT 모델을 호출하여 커밋 메시지를 생성합니다."""

import os
from typing import Final, Any, cast
from openai import OpenAI


_DEFAULT_MODEL: Final[str] = "gpt-5-mini"

# 시스템 프롬프트를 상수로 유지하여 중복을 제거합니다.
_SYSTEM_PROMPT: Final[str] = (
    "You are an expert Git commit message generator. "
    "Always use British English (en-GB) spelling and style. "
    "Write a single-line imperative subject (<=72 chars); add a body with bullet points when beneficial. "
    "Explain the intent and rationale briefly. "
    "Consider the user-provided auxiliary context if present. "
    "Return only the commit message text, without labels or code fences."
)


def _system_message() -> dict[str, str]:
    """시스템 메시지 딕셔너리를 생성합니다."""
    return {"role": "system", "content": _SYSTEM_PROMPT}


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
) -> str:
    """OpenAI GPT 모델을 호출하여 커밋 메시지를 생성합니다."""

    chosen_model: str = _resolve_model(model=model)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수가 필요합니다.")

    client = OpenAI(api_key=api_key)

    _combined_prompt, user_messages = _build_user_messages(diff=diff, hint=hint)

    # Chat Completions API를 사용해 한 번의 응답을 생성 (hint와 diff를 별도 user 메시지로 전송)
    all_messages: list[dict[str, str]] = [_system_message(), *user_messages]

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

    all_messages = [_system_message(), *user_messages]

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
