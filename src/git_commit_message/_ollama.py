"""Ollama provider implementation.

Mirrors the Gemini provider structure: a single provider class that exposes
`generate_text` and `count_tokens`. Provider-agnostic orchestration lives in
`_llm.py`.
"""

from __future__ import annotations

from typing import ClassVar

from ollama import Client, ResponseError

from ._config import resolve_provider_url
from ._llm import LLMTextResult, LLMUsage


class OllamaProvider:
    """Ollama provider implementation for the LLM protocol."""

    __slots__ = (
        "_host",
        "_client",
    )

    name: ClassVar[str] = "ollama"

    def __init__(
        self,
        /,
        *,
        host: str | None = None,
        url: str | None = None,
    ) -> None:
        self._host = resolve_provider_url("ollama", url=url, host=host)
        self._client = Client(host=self._host)

    def generate_text(
        self,
        /,
        *,
        model: str,
        instructions: str,
        user_text: str,
    ) -> LLMTextResult:
        """Generate text using Ollama (non-streaming)."""

        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_text},
        ]

        try:
            response = self._client.chat(model=model, messages=messages)
        except ResponseError as exc:
            raise RuntimeError(
                f"Ollama API error: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Failed to connect to Ollama at {self._host}. Make sure Ollama is running: {exc}"
            ) from exc

        response_text = response.message.content or ""

        # Extract token usage if available
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        total_tokens: int | None = None

        if hasattr(response, "prompt_eval_count") and response.prompt_eval_count:
            prompt_tokens = response.prompt_eval_count
        if hasattr(response, "eval_count") and response.eval_count:
            completion_tokens = response.eval_count
        if prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        return LLMTextResult(
            text=response_text.strip(),
            response_id=None,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
        )

    def count_tokens(
        self,
        /,
        *,
        model: str,
        text: str,
    ) -> int:
        raise RuntimeError(
            "Token counting is not supported for the Ollama provider. "
            "Try `--chunk-tokens 0` (default) or `--chunk-tokens -1` to disable summarisation."
        )
