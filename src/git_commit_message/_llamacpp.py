"""llama.cpp native HTTP API calls and token counting.

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
    """Use the native API of a server with a pre-loaded model."""

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
                "Check that the server supports the required native API."
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
        """Apply the server's chat template, then generate a completion.

        :param model: Kept for protocol compatibility; the server's loaded model is used.
        """

        template = self._post("/apply-template", {
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_text},
            ],
        })
        prompt = template.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise RuntimeError("llama.cpp /apply-template returned an invalid or empty prompt.")

        response = self._post("/completion", {"prompt": prompt, "stream": False})
        content = response.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("llama.cpp /completion returned invalid or empty response text.")
        truncated = response.get("truncated")
        stop_type = response.get("stop_type")
        if truncated is not None and type(truncated) is not bool:
            raise RuntimeError("llama.cpp /completion returned an invalid truncated flag.")
        if stop_type is not None and stop_type not in ("eos", "word", "limit"):
            raise RuntimeError("llama.cpp /completion returned an invalid stop_type.")
        if truncated is True or stop_type == "limit":
            raise RuntimeError(
                "llama.cpp /completion returned an incomplete response (context or generation limit). "
                "Increase the server limit or reduce the input/chunk size."
            )

        counts: list[int | None] = []
        for field in ("tokens_evaluated", "tokens_predicted"):
            count = response.get(field)
            if count is None:
                counts.append(None)
                continue
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise RuntimeError(f"llama.cpp /completion returned invalid {field}.")
            counts.append(count)
        prompt_tokens, completion_tokens = counts
        total_tokens = (
            prompt_tokens + completion_tokens
            if prompt_tokens is not None and completion_tokens is not None
            else None
        )
        return LLMTextResult(
            text=content.strip(),
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
