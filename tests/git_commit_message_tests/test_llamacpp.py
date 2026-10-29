"""Verify native llama.cpp requests, failures, and orchestration."""

from __future__ import annotations

from io import BytesIO
from json import dumps, loads
from unittest import TestCase, main
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from git_commit_message._llamacpp import LlamaCppProvider, _resolve_llamacpp_host
from git_commit_message._llm import generate_commit_message_with_info


class LlamaCppTests(TestCase):
    __slots__ = ()

    def test_host_precedence(
        self,
        /,
    ) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(_resolve_llamacpp_host(None), "http://localhost:8080")
        with patch.dict("os.environ", {"LLAMACPP_HOST": "http://env:8081/"}):
            self.assertEqual(_resolve_llamacpp_host(None), "http://env:8081")
            self.assertEqual(_resolve_llamacpp_host("http://arg:8082///"), "http://arg:8082")

    def test_native_requests_and_usage(
        self,
        /,
    ) -> None:
        with patch("git_commit_message._llamacpp.urlopen", side_effect=[
            BytesIO(dumps({"prompt": " formatted prompt\n"}).encode()),
            BytesIO(dumps({"content": " result \n", "tokens_evaluated": 12,
                          "tokens_predicted": 3, "truncated": False, "stop_type": "eos"}).encode()),
        ]) as send:
            result = LlamaCppProvider(host="http://server/").generate_text(
                model="ignored", instructions="system", user_text="한글 diff",
            )
        requests = [call.args[0] for call in send.call_args_list]
        self.assertEqual([request.full_url for request in requests], [
            "http://server/apply-template", "http://server/completion",
        ])
        self.assertEqual(loads(requests[0].data), {"messages": [
            {"role": "system", "content": "system"}, {"role": "user", "content": "한글 diff"},
        ]})
        self.assertEqual(loads(requests[1].data), {"prompt": " formatted prompt\n", "stream": False})
        for call in send.call_args_list:
            self.assertEqual(call.kwargs, {"timeout": 600})
            self.assertEqual(call.args[0].get_method(), "POST")
            self.assertEqual(call.args[0].get_header("Content-type"), "application/json")
        self.assertEqual(result.text, "result")
        self.assertIsNone(result.response_id)
        self.assertEqual((result.usage.prompt_tokens, result.usage.completion_tokens,
                          result.usage.total_tokens), (12, 3, 15))

    def test_missing_and_partial_usage(
        self,
        /,
    ) -> None:
        for fields, expected in [({}, (None, None, None)),
                                 ({"tokens_evaluated": 0}, (0, None, None)),
                                 ({"tokens_evaluated": 0, "tokens_predicted": 0}, (0, 0, 0))]:
            with self.subTest(fields=fields), patch.object(LlamaCppProvider, "_post", side_effect=[
                {"prompt": "prompt"}, {"content": "ok", **fields},
            ]):
                result = LlamaCppProvider().generate_text(model="default", instructions="s", user_text="u")
                self.assertEqual((result.usage.prompt_tokens, result.usage.completion_tokens,
                                  result.usage.total_tokens), expected)

    def test_tokenize_request(
        self,
        /,
    ) -> None:
        for tokens in ([], [1, 2, 3]):
            with self.subTest(tokens=tokens), patch("git_commit_message._llamacpp.urlopen",
                                                   return_value=BytesIO(dumps({"tokens": tokens}).encode())) as send:
                self.assertEqual(LlamaCppProvider().count_tokens(model="ignored", text="<|im_end|>"), len(tokens))
                self.assertEqual(send.call_args.args[0].full_url, "http://localhost:8080/tokenize")
                self.assertEqual(loads(send.call_args.args[0].data), {
                    "content": "<|im_end|>", "add_special": False,
                    "parse_special": False, "with_pieces": False,
                })

    def test_invalid_native_responses(
        self,
        /,
    ) -> None:
        cases = [
            ([{}], "prompt"),
            ([{"prompt": 42}], "prompt"),
            ([{"prompt": " "}], "prompt"),
            ([{"prompt": "p"}, {}], "response text"),
            ([{"prompt": "p"}, {"content": []}], "response text"),
            ([{"prompt": "p"}, {"content": " "}], "response text"),
            ([{"prompt": "p"}, {"content": "partial", "truncated": True}], "incomplete"),
            ([{"prompt": "p"}, {"content": "partial", "stop_type": "limit"}], "incomplete"),
            ([{"prompt": "p"}, {"content": "ok", "truncated": "false"}], "truncated"),
            ([{"prompt": "p"}, {"content": "ok", "stop_type": "none"}], "stop_type"),
        ]
        for field in ("tokens_evaluated", "tokens_predicted"):
            for value in (True, -1, "3", 2.5):
                cases.append(([{"prompt": "p"}, {"content": "ok", field: value}], field))
        for responses, error in cases:
            with self.subTest(responses=responses), patch.object(LlamaCppProvider, "_post", side_effect=responses):
                with self.assertRaisesRegex(RuntimeError, error):
                    LlamaCppProvider().generate_text(model="default", instructions="s", user_text="u")
        for tokens in (None, "123", [True], [-1], [{}], [1.5]):
            with self.subTest(tokens=tokens), patch.object(LlamaCppProvider, "_post", return_value={"tokens": tokens}):
                with self.assertRaisesRegex(RuntimeError, "/tokenize"):
                    LlamaCppProvider().count_tokens(model="default", text="x")

    def test_transport_errors_without_retry(
        self,
        /,
    ) -> None:
        for error, expected in [
            (HTTPError("http://localhost:8080/tokenize", 404, "Not Found", {}, None), "HTTP 404"),
            (HTTPError("http://localhost:8080/tokenize", 503, "Unavailable", {}, None), "HTTP 503"),
            (URLError("connection refused"), "connection refused"),
            (TimeoutError("timed out"), "timed out"),
        ]:
            with self.subTest(error=error), patch("git_commit_message._llamacpp.urlopen", side_effect=error) as send:
                with self.assertRaisesRegex(RuntimeError, f"/tokenize.*{expected}"):
                    LlamaCppProvider().count_tokens(model="default", text="x")
                self.assertEqual(send.call_count, 1)
        for payload in (b"not JSON", b"\xff", b"[]", b"null"):
            with self.subTest(payload=payload), patch("git_commit_message._llamacpp.urlopen", return_value=BytesIO(payload)):
                with self.assertRaisesRegex(RuntimeError, "/tokenize"):
                    LlamaCppProvider().count_tokens(model="default", text="x")

    def test_all_summary_paths(
        self,
        /,
    ) -> None:
        diff = (
            "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
            "diff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n-before\n+after\n"
        )
        for budget, generations in [(-1, 1), (0, 2), (1, 3)]:
            paths: list[str] = []

            def respond(
                request: Request,
                /,
                *,
                timeout: int,
            ) -> BytesIO:
                path = request.full_url.rsplit("/", 1)[-1]
                paths.append(path)
                body = loads(request.data)
                if path == "tokenize":
                    result = {"tokens": list(range(body["content"].count("diff --git")))}
                elif path == "apply-template":
                    self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])
                    result = {"prompt": "formatted"}
                else:
                    self.assertEqual(path, "completion")
                    result = {"content": "generated", "tokens_evaluated": 5, "tokens_predicted": 2}
                return BytesIO(dumps(result).encode())

            with self.subTest(budget=budget), patch("git_commit_message._llamacpp.urlopen", side_effect=respond):
                result = generate_commit_message_with_info(
                    diff, None, "default", False, None, "ko-KR", budget, "llamacpp",
                )
                self.assertEqual(result.message, "generated")
                self.assertEqual(result.total_tokens, generations * 7)
                self.assertEqual(paths.count("completion"), generations)
                self.assertEqual(paths.count("apply-template"), generations)
                self.assertEqual("tokenize" in paths, budget > 0)


if __name__ == "__main__":
    main()
