"""Direct llama.cpp HTTP API calls and token counting.

Provider-agnostic orchestration/prompt logic lives in `_llm.py`.
"""

from __future__ import annotations

from json import JSONDecodeError, dumps, loads
from os import environ
from typing import ClassVar, Final
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ._llm import LLMTextResult, LLMUsage


_DEFAULT_LLAMACPP_HOST: Final[str] = "http://localhost:8080"
_REQUEST_TIMEOUT: Final[int] = 600


def _resolve_llamacpp_host(
    host: str | None,
    /,
) -> str:
    """Resolve the server root URL from arg, env, or default."""

    return (host or environ.get("LLAMACPP_HOST") or _DEFAULT_LLAMACPP_HOST).rstrip("/")


class LlamaCppProvider:
    """Use the chat and tokenisation APIs of a server with a pre-loaded model."""

    __slots__ = ("_host",)

    name: ClassVar[str] = "llamacpp"

    def __init__(
        self,
        /,
        *,
        host: str | None = None,
    ) -> None:
        self._host = _resolve_llamacpp_host(host)

    def _post(
        self,
        path: str,
        body: dict[str, object],
        /,
    ) -> dict[str, object]:
        """Send one JSON request without automatic retries."""

        url = f"{self._host}{path}"
        request = Request(
            url,
            data=dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=_REQUEST_TIMEOUT) as response:
                result = loads(response.read())
        except HTTPError as exc:
            raise RuntimeError(
                f"llama.cpp request to {url} failed: HTTP {exc.code} {exc.reason}. "
                "Check that the server supports the required API endpoint."
            ) from exc
        except (URLError, OSError) as exc:
            raise RuntimeError(f"llama.cpp request to {url} failed: {exc}") from exc
        except (JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"llama.cpp returned invalid JSON from {url}.") from exc

        if not isinstance(result, dict):
            raise RuntimeError(f"llama.cpp returned an unexpected response from {url}.")
        return result

    def generate_text(
        self,
        /,
        *,
        model: str,
        instructions: str,
        user_text: str,
    ) -> LLMTextResult:
        """Return only the final assistant content from the server's chat API.

        Chat formatting and reasoning separation are the server's responsibility.
        :param model: Kept for protocol compatibility; the server's loaded model is used.
        """

        response = self._post("/chat/completions", {
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_text},
            ],
            "stream": False,
        })
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise RuntimeError("llama.cpp /chat/completions returned invalid choices.")
        choice = choices[0]
        if choice.get("finish_reason") != "stop":
            raise RuntimeError(
                "llama.cpp /chat/completions did not finish with a complete text answer "
                f"(finish_reason={choice.get('finish_reason')!r}). "
                "Check the server limits and configuration."
            )
        if response.get("truncated") is True:
            raise RuntimeError("llama.cpp /chat/completions returned a context-truncated response.")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("llama.cpp /chat/completions returned an invalid message.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("llama.cpp /chat/completions returned invalid or empty final answer text.")

        usage_data = response.get("usage")
        usage: LLMUsage | None = None
        if usage_data is not None:
            if not isinstance(usage_data, dict):
                raise RuntimeError("llama.cpp /chat/completions returned invalid usage.")
            counts: list[int | None] = []
            for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
                count = usage_data.get(field)
                if count is None:
                    counts.append(None)
                    continue
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise RuntimeError(f"llama.cpp /chat/completions returned invalid {field}.")
                counts.append(count)
            prompt_tokens, completion_tokens, total_tokens = counts
            if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
                total_tokens = prompt_tokens + completion_tokens
            usage = LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        response_id = response.get("id")
        if response_id is not None and not isinstance(response_id, str):
            raise RuntimeError("llama.cpp /chat/completions returned an invalid response ID.")
        return LLMTextResult(
            text=content.strip(),
            response_id=response_id,
            usage=usage,
        )

    def count_tokens(
        self,
        /,
        *,
        model: str,
        text: str,
    ) -> int:
        """Count raw diff tokens, excluding chat-template and special-token overhead.

        This count does not guarantee that the full generation fits the context.
        :param model: Kept for protocol compatibility; the server's loaded model is used.
        """

        response = self._post("/tokenize", {
            "content": text,
            "add_special": False,
            "parse_special": False,
            "with_pieces": False,
        })
        tokens = response.get("tokens")
        if not isinstance(tokens, list) or any(type(token) is not int or token < 0 for token in tokens):
            raise RuntimeError("llama.cpp /tokenize returned an invalid tokens array.")
        return len(tokens)
