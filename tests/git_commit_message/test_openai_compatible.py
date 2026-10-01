"""Exercise OpenAI-compatible requests without external network access."""

from __future__ import annotations

from contextlib import ExitStack
from io import StringIO
from json import loads
from os import environ
from pathlib import Path
from typing import Any
from unittest import TestCase, main
from unittest.mock import patch

from httpx import Client, MockTransport, Request, Response
from openai import OpenAI

from git_commit_message._cli import _build_parser, _run
from git_commit_message._gpt import OpenAIResponsesProvider
from git_commit_message._llm import generate_commit_message, generate_commit_message_with_info


class OpenAICompatibleTests(TestCase):
    __slots__ = ()

    def _chat_response(
        self,
        /,
        *,
        content: str | None = "feat: support router",
        choices: bool = True,
        usage: bool = True,
    ) -> dict[str, Any]:
        return {
            "id": "chat-test", "object": "chat.completion", "created": 1,
            "model": "router-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": content,
            }}] if choices else [],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10} if usage else None,
        }

    def test_configuration_precedence_and_optional_key(
        self,
        /,
    ) -> None:
        with patch.dict(environ, {"OPENAI_BASE_URL": "http://environment/v1", "GIT_COMMIT_MESSAGE_OPENAI_API": "chat-completions"}, clear=True), patch("git_commit_message._gpt.OpenAI") as factory:
            OpenAIResponsesProvider(host="http://explicit/v1", api="responses")
            factory.assert_called_once_with(api_key="unused", base_url="http://explicit/v1")
        with patch.dict(environ, {"OPENAI_BASE_URL": "http://environment/v1", "OPENAI_API_KEY": "environment-key"}, clear=True), patch("git_commit_message._gpt.OpenAI") as factory:
            OpenAIResponsesProvider(api_key="explicit-key")
            factory.assert_called_once_with(api_key="explicit-key", base_url="http://environment/v1")
        with patch.dict(environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                OpenAIResponsesProvider()
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                OpenAIResponsesProvider(host="https://api.openai.com/v1")
            with self.assertRaisesRegex(ValueError, "OpenAI API"):
                OpenAIResponsesProvider(api="invalid")
        with patch.dict(environ, {"GIT_COMMIT_MESSAGE_OPENAI_API": "invalid"}, clear=True):
            with self.assertRaises(ValueError):
                OpenAIResponsesProvider()

    def test_chat_request_and_response_mapping(
        self,
        /,
    ) -> None:
        requests: list[Request] = []

        def handle(
            request: Request,
            /,
        ) -> Response:
            requests.append(request)
            return Response(200, json=self._chat_response(content="  feat: support router\n "))

        with Client(transport=MockTransport(handle)) as http_client, OpenAI(api_key="unused", base_url="http://router/v1", http_client=http_client) as client, patch.dict(environ, {}, clear=True), patch("git_commit_message._gpt.OpenAI", return_value=client):
            provider = OpenAIResponsesProvider(host="http://router/v1", api="chat-completions")
            result = provider.generate_text(model="router-model", instructions="Rules", user_text="Diff")
            self.assertEqual(result.text, "feat: support router")
            self.assertEqual(result.response_id, "chat-test")
            self.assertIsNotNone(result.usage)
            assert result.usage is not None
            self.assertEqual((result.usage.prompt_tokens, result.usage.completion_tokens, result.usage.total_tokens), (7, 3, 10))
            with self.assertRaisesRegex(RuntimeError, "Token counting is unavailable"):
                provider.count_tokens(model="router-model", text="Diff")
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), "http://router/v1/chat/completions")
        self.assertEqual(loads(requests[0].content), {"model": "router-model", "messages": [{"role": "system", "content": "Rules"}, {"role": "user", "content": "Diff"}], "stream": False})

    def test_empty_chat_results_and_missing_usage(
        self,
        /,
    ) -> None:
        for content, choices in ((None, True), ("  ", True), ("ignored", False)):
            with self.subTest(content=content, choices=choices), Client(transport=MockTransport(lambda request: Response(200, json=self._chat_response(content=content, choices=choices)))) as http_client, OpenAI(api_key="unused", base_url="http://router/v1", http_client=http_client) as client, patch.dict(environ, {}, clear=True), patch("git_commit_message._gpt.OpenAI", return_value=client):
                with self.assertRaisesRegex(RuntimeError, "empty response"):
                    OpenAIResponsesProvider(host="http://router/v1", api="chat-completions").generate_text(model="model", instructions="Rules", user_text="Diff")
        with Client(transport=MockTransport(lambda request: Response(200, json=self._chat_response(usage=False)))) as http_client, OpenAI(api_key="unused", base_url="http://router/v1", http_client=http_client) as client, patch.dict(environ, {}, clear=True), patch("git_commit_message._gpt.OpenAI", return_value=client):
            result = OpenAIResponsesProvider(host="http://router/v1", api="chat-completions").generate_text(model="model", instructions="Rules", user_text="Diff")
            self.assertIsNone(result.usage)

    def test_default_responses_contract(
        self,
        /,
    ) -> None:
        requests: list[Request] = []

        def handle(
            request: Request,
            /,
        ) -> Response:
            requests.append(request)
            return Response(200, json={"id": "response-test", "object": "response", "created_at": 1, "model": "model", "status": "completed", "output": [{"id": "message-test", "type": "message", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": "fix: preserve defaults", "annotations": []}]}], "usage": {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6}})

        with Client(transport=MockTransport(handle)) as http_client, OpenAI(api_key="test-key", http_client=http_client) as client, patch.dict(environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch("git_commit_message._gpt.OpenAI", return_value=client):
            result = OpenAIResponsesProvider().generate_text(model="model", instructions="Rules", user_text="Diff")
        self.assertEqual(result.text, "fix: preserve defaults")
        self.assertEqual(requests[0].url.path, "/v1/responses")
        self.assertEqual(loads(requests[0].content), {"model": "model", "instructions": "Rules", "input": [{"role": "user", "content": [{"type": "input_text", "text": "Diff"}]}]})

    def test_generation_modes_use_chat_for_all_calls(
        self,
        /,
    ) -> None:
        for generator in (generate_commit_message, generate_commit_message_with_info):
            for chunk_tokens, expected_calls in ((0, 2), (-1, 1)):
                requests: list[Request] = []

                def handle(
                    request: Request,
                    /,
                ) -> Response:
                    requests.append(request)
                    return Response(200, json=self._chat_response())

                with self.subTest(generator=generator.__name__, chunk_tokens=chunk_tokens), Client(transport=MockTransport(handle)) as http_client, OpenAI(api_key="unused", base_url="http://router/v1", http_client=http_client) as client, patch.dict(environ, {}, clear=True), patch("git_commit_message._gpt.OpenAI", return_value=client):
                    result = generator("diff --git a/a b/a\n@@ -1 +1 @@\n-old\n+new\n", None, "router-model", False, None, None, chunk_tokens, "openai", "http://router/v1", False, openai_api="chat-completions")
                self.assertEqual(len(requests), expected_calls)
                self.assertTrue(all(request.url.path == "/v1/chat/completions" for request in requests))
                self.assertEqual(result if isinstance(result, str) else result.message, "feat: support router")
                if not isinstance(result, str):
                    self.assertEqual(result.total_tokens, 10 * expected_calls)

    def test_chat_positive_budget_rejects_metadata_only_diff(
        self,
        /,
    ) -> None:
        metadata_diff = "diff --git a/old b/new\nsimilarity index 100%\nrename from old\nrename to new\n"
        for generator in (generate_commit_message, generate_commit_message_with_info):
            for api, environment in (("chat-completions", {}), (None, {"GIT_COMMIT_MESSAGE_OPENAI_API": "chat-completions"})):
                with self.subTest(generator=generator.__name__, api=api), patch.dict(environ, environment, clear=True), patch("git_commit_message._gpt.OpenAI") as factory:
                    with self.assertRaisesRegex(ValueError, "Positive --chunk-tokens"):
                        generator(metadata_diff, None, "model", False, None, None, 100, "openai", "http://router/v1", False, openai_api=api)
                    factory.return_value.chat.completions.create.assert_not_called()

    def test_cli_forwards_custom_host_and_api(
        self,
        /,
    ) -> None:
        with patch.dict(environ, {}, clear=True):
            arguments = _build_parser().parse_args(["--provider", "openai", "--host", "http://router/v1", "--openai-api", "chat-completions", "--no-branch", "--no-log"])
            with ExitStack() as stack:
                stack.enter_context(patch("git_commit_message._cli.get_repo_root", return_value=Path("/repository")))
                stack.enter_context(patch("git_commit_message._cli.has_staged_changes", return_value=True))
                stack.enter_context(patch("git_commit_message._cli.get_staged_diff", return_value="diff"))
                stack.enter_context(patch("sys.stdout", new=StringIO()))
                generate = stack.enter_context(patch("git_commit_message._cli.generate_commit_message", return_value="feat: router"))
                self.assertEqual(_run(arguments), 0)
            self.assertEqual(generate.call_args.args[8], "http://router/v1")
            self.assertEqual(generate.call_args.kwargs["openai_api"], "chat-completions")
            with patch("sys.stderr", new=StringIO()), self.assertRaises(SystemExit):
                _build_parser().parse_args(["--openai-api", "invalid"])


if __name__ == "__main__":
    main()
