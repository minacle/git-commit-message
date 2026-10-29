"""Verify llama.cpp host resolution and tokenisation transport."""

from __future__ import annotations

from io import BytesIO
from json import dumps, loads
from unittest import TestCase, main
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from git_commit_message._llamacpp import LlamaCppProvider, _resolve_llamacpp_host


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

    def test_tokenize_request(
        self,
        /,
    ) -> None:
        for tokens in ([], [1, 2, 3]):
            with self.subTest(tokens=tokens), patch("git_commit_message._llamacpp.urlopen",
                                                   return_value=BytesIO(dumps({"tokens": tokens}).encode())) as send:
                self.assertEqual(LlamaCppProvider(host="http://localhost:8080").count_tokens(model="ignored", text="<|im_end|>"), len(tokens))
                self.assertEqual(send.call_args.args[0].full_url, "http://localhost:8080/tokenize")
                self.assertEqual(loads(send.call_args.args[0].data), {
                    "content": "<|im_end|>", "add_special": False,
                    "parse_special": False, "with_pieces": False,
                })

    def test_invalid_tokenize_responses(
        self,
        /,
    ) -> None:
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


if __name__ == "__main__":
    main()
