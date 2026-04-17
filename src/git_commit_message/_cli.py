"""Command-line interface entry point.

Collect staged changes from the repository and call an LLM provider
to generate a commit message, or create a commit straight away.
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from os import environ
from pathlib import Path
import re
from re import Pattern
from sys import exit as sys_exit
from sys import stderr
from typing import Final

from ._git import (
    commit_with_message,
    get_current_branch,
    get_git_log,
    get_repo_root,
    get_staged_diff,
    has_head_commit,
    has_staged_changes,
    resolve_amend_base_ref,
)
from ._config import resolve_provider_name, validate_provider_chunk_tokens
from ._llm import (
    CommitMessageResult,
    UnsupportedProviderError,
    generate_commit_message,
    generate_commit_message_with_info,
)


class CliArgs(Namespace):
    __slots__ = (
        "description",
        "commit",
        "amend",
        "edit",
        "conventional",
        "provider",
        "model",
        "language",
        "debug",
        "one_line",
        "max_length",
        "chunk_tokens",
        "diff_context",
        "no_branch",
        "no_log",
        "log_count",
        "host",
        "co_authors",
    )

    def __init__(
        self,
        /,
    ) -> None:
        self.description: str | None = None
        self.commit: bool = False
        self.amend: bool = False
        self.edit: bool = False
        self.conventional: bool = False
        self.provider: str | None = None
        self.model: str | None = None
        self.language: str | None = None
        self.debug: bool = False
        self.one_line: bool = False
        self.max_length: int | None = None
        self.chunk_tokens: int | None = None
        self.diff_context: int | None = None
        self.no_branch: bool = False
        self.no_log: bool = False
        self.log_count: int = 10
        self.host: str | None = None
        self.co_authors: list[str] | None = None


_CO_AUTHOR_LINE_RE: Final[Pattern[str]] = re.compile(
    r"^\s*([^<>\s\n][^<>\n]*?)\s*<([^<>\s\n]+@[^<>\s\n]+)>\s*$"
)
_CO_AUTHOR_ALIASES: Final[dict[str, str]] = {
    "claude-code": "Claude <noreply@anthropic.com>",
    "codex": "Codex <noreply@openai.com>",
    "copilot": "Copilot <copilot@github.com>",
    "copilot-cli": "Copilot <223556219+Copilot@users.noreply.github.com>",
}


def _co_author_alias_keywords_text() -> str:
    """Return a readable list of accepted co-author alias keywords."""

    keywords: list[str] = sorted(_CO_AUTHOR_ALIASES.keys())
    return ", ".join(f"'{keyword}'" for keyword in keywords)


def _normalize_co_author(
    raw: str,
    /,
) -> str:
    """Normalize one co-author input into ``Name <email>`` form."""

    value: str = raw.strip()
    if not value:
        raise ValueError("Co-author cannot be empty.")

    alias: str | None = _CO_AUTHOR_ALIASES.get(value.lower())
    if alias is not None:
        return alias

    match = _CO_AUTHOR_LINE_RE.match(value)
    if match is None:
        raise ValueError(
            "Invalid co-author format: use 'Name <email@example.com>' "
            f"or an alias keyword ({_co_author_alias_keywords_text()})."
        )

    name: str = match.group(1).strip()
    email: str = match.group(2).strip()
    return f"{name} <{email}>"


def _append_co_author_footers(
    message: str,
    normalized_co_authors: list[str],
    /,
) -> str:
    """Append Git co-author trailers to a commit message."""

    if not normalized_co_authors:
        return message

    base: str = message.rstrip()
    footer_lines: list[str] = [
        f"Co-authored-by: {author}" for author in normalized_co_authors
    ]
    return f"{base}\n\n" + "\n".join(footer_lines)


def _normalize_co_authors(
    co_authors: list[str],
    /,
) -> list[str]:
    """Normalize and deduplicate co-author values in insertion order."""

    seen: set[str] = set()
    normalized: list[str] = []
    for raw in co_authors:
        author = _normalize_co_author(raw)
        key = author.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(author)
    return normalized


def _env_chunk_tokens_default() -> int | None:
    """Return chunk token default from env if valid, else None."""

    raw: str | None = environ.get("GIT_COMMIT_MESSAGE_CHUNK_TOKENS")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _env_diff_context_default() -> int | None:
    """Return diff context default from env.

    Raises
    ------
    ValueError
        If the configured value is not an integer.
    """

    raw: str | None = environ.get("GIT_COMMIT_MESSAGE_DIFF_CONTEXT")
    if raw is None:
        return None
    return int(raw)


def _build_parser() -> ArgumentParser:
    """Create the CLI argument parser.

    Returns
    -------
    ArgumentParser
        A configured argument parser.
    """

    parser: ArgumentParser = ArgumentParser(
        prog="git-commit-message",
        description=(
            "Generate a commit message based on the staged changes."
        ),
    )

    parser.add_argument(
        "description",
        nargs="?",
        help="Optional auxiliary description of the changes.",
    )

    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit immediately with the generated message.",
    )

    parser.add_argument(
        "--amend",
        action="store_true",
        help=(
            "Generate a message suitable for amending the previous commit. "
            "When set, the diff is computed from the amended commit's parent to the staged index. "
            "Use with '--commit' to run the amend, or omit '--commit' to print the message only."
        ),
    )

    parser.add_argument(
        "--edit",
        action="store_true",
        help="Open an editor to amend the message before committing. Use with '--commit'.",
    )

    parser.add_argument(
        "--conventional",
        action="store_true",
        help=(
            "Use Conventional Commits constraints for the subject line and footer. "
            "The existing body format remains unchanged, including the translated Rationale line."
        ),
    )

    parser.add_argument(
        "--provider",
        default=None,
        help=(
            "LLM provider to use (default: openai). "
            "You may also set GIT_COMMIT_MESSAGE_PROVIDER. "
            "The CLI flag overrides the environment variable. "
            "Supported providers: openai, google, ollama, llamacpp."
        ),
    )

    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Model name to use. If unspecified, uses GIT_COMMIT_MESSAGE_MODEL or a provider-specific default "
            "(openai: gpt-5-mini; google: gemini-2.5-flash; ollama: gpt-oss:20b; llamacpp: default)."
        ),
    )

    parser.add_argument(
        "--language",
        dest="language",
        default=None,
        help=(
            "Target language/locale IETF tag for the output (default: en-GB). "
            "You may also set GIT_COMMIT_MESSAGE_LANGUAGE."
        ),
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print the request/response and token usage.",
    )

    parser.add_argument(
        "--one-line",
        dest="one_line",
        action="store_true",
        help="Use only a single-line subject.",
    )

    parser.add_argument(
        "--max-length",
        dest="max_length",
        type=int,
        default=None,
        help="Maximum subject (first line) length (default: 72).",
    )

    parser.add_argument(
        "--chunk-tokens",
        dest="chunk_tokens",
        type=int,
        default=None,
        help=(
            "Target token budget per diff chunk. "
            "0 forces a single chunk with summarisation; -1 disables summarisation (legacy one-shot). "
            "For provider 'ollama', values >= 1 are not supported. "
            "If omitted, uses GIT_COMMIT_MESSAGE_CHUNK_TOKENS when set (default: 0)."
        ),
    )

    parser.add_argument(
        "--diff-context",
        dest="diff_context",
        type=int,
        default=None,
        help=(
            "Number of context lines in unified diff output. "
            "If omitted, uses GIT_COMMIT_MESSAGE_DIFF_CONTEXT when set "
            "(default: Git default, usually 3)."
        ),
    )

    parser.add_argument(
        "--no-branch",
        dest="no_branch",
        action="store_true",
        help="Do not include the current branch name in the LLM context.",
    )

    parser.add_argument(
        "--no-log",
        dest="no_log",
        action="store_true",
        help="Do not include recent Git log entries in the LLM context.",
    )

    parser.add_argument(
        "--log-count",
        dest="log_count",
        type=int,
        default=10,
        help=(
            "Number of recent Git log entries to include in the LLM context "
            "(default: 10). Ignored when --no-log is set."
        ),
    )

    parser.add_argument(
        "--host",
        dest="host",
        default=None,
        help=(
            "Host URL for API providers like Ollama or llama.cpp "
            "(default: http://localhost:11434 for Ollama, http://localhost:8080 for llama.cpp). "
            "You may also set OLLAMA_HOST for Ollama or LLAMACPP_HOST for llama.cpp."
        ),
    )

    parser.add_argument(
        "--co-author",
        dest="co_authors",
        action="append",
        default=None,
        help=(
            "Add Co-authored-by trailer(s) to the generated message. "
            "Repeat for multiple co-authors. "
            "Use 'Name <email@example.com>' or an alias keyword "
            f"({_co_author_alias_keywords_text()}). "
            "When used with --one-line, the subject line remains single-line and these "
            "trailers are appended on separate lines (i.e., the overall output is multi-line)."
        ),
    )

    return parser


def _run(
    args: CliArgs,
    /,
) -> int:
    """Main execution logic.

    Parameters
    ----------
    args
        Parsed CLI arguments.

    Returns
    -------
    int
        Process exit code. 0 indicates success; any other value indicates failure.
    """

    chunk_tokens: int | None = args.chunk_tokens
    if chunk_tokens is None:
        chunk_tokens = _env_chunk_tokens_default()
    if chunk_tokens is None:
        chunk_tokens = 0

    diff_context: int | None = args.diff_context
    if diff_context is None:
        try:
            diff_context = _env_diff_context_default()
        except ValueError:
            print(
                "GIT_COMMIT_MESSAGE_DIFF_CONTEXT must be an integer.",
                file=stderr,
            )
            return 2
    if diff_context is not None and diff_context < 0:
        print("--diff-context must be greater than or equal to 0.", file=stderr)
        return 2

    if not args.no_log and args.log_count < 1:
        print("--log-count must be greater than or equal to 1.", file=stderr)
        return 2

    provider_name: str = resolve_provider_name(args.provider)
    provider_arg_error = validate_provider_chunk_tokens(provider_name, chunk_tokens)
    if provider_arg_error is not None:
        print(provider_arg_error, file=stderr)
        return 2

    repo_root: Path = get_repo_root()

    if args.amend:
        if not has_head_commit(repo_root):
            print("Cannot amend: the repository has no commits yet.", file=stderr)
            return 2

        base_ref = resolve_amend_base_ref(repo_root)
        diff_text: str = get_staged_diff(
            repo_root,
            base_ref=base_ref,
            context_lines=diff_context,
        )
    else:
        if not has_staged_changes(repo_root):
            print("No staged changes. Run 'git add' and try again.", file=stderr)
            return 2

        diff_text = get_staged_diff(repo_root, context_lines=diff_context)

    branch: str | None = None if args.no_branch else get_current_branch(repo_root)
    log: str | None = None if args.no_log else get_git_log(repo_root, count=args.log_count)

    hint: str | None = args.description if isinstance(args.description, str) else None

    normalized_co_authors: list[str] | None = None
    if args.co_authors:
        try:
            normalized_co_authors = _normalize_co_authors(args.co_authors)
        except ValueError as exc:
            print(str(exc), file=stderr)
            return 2

    result: CommitMessageResult | None = None
    try:
        if args.debug:
            result = generate_commit_message_with_info(
                diff_text,
                hint,
                args.model,
                args.one_line,
                args.max_length,
                args.language,
                chunk_tokens,
                args.provider,
                args.host,
                args.conventional,
                branch=branch,
                log=log,
            )
            message = result.message
        else:
            message = generate_commit_message(
                diff_text,
                hint,
                args.model,
                args.one_line,
                args.max_length,
                args.language,
                chunk_tokens,
                args.provider,
                args.host,
                args.conventional,
                branch=branch,
                log=log,
            )
    except UnsupportedProviderError as exc:
        print(str(exc), file=stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 - to preserve standard output messaging
        print(f"Failed to generate commit message: {exc}", file=stderr)
        return 3

    # Option: force single-line message
    if args.one_line:
        # Use the first non-empty line only
        for line in (ln.strip() for ln in message.splitlines()):
            if line:
                message = line
                break
        else:
            message = ""

    # Defensive check: one-line normalization can result in an empty message.
    if not message.strip():
        print("Failed to generate commit message: generated message is empty.", file=stderr)
        return 3

    if normalized_co_authors:
        message = _append_co_author_footers(message, normalized_co_authors)

    if not args.commit:
        if args.debug and result is not None:
            # Print debug information
            print(f"==== {result.provider} Usage ====")
            print(f"provider: {result.provider}")
            print(f"model: {result.model}")
            print(f"response_id: {result.response_id or '(n/a)'}")
            if result.total_tokens is not None:
                print(
                    f"tokens: prompt={result.prompt_tokens} completion={result.completion_tokens} total={result.total_tokens}"
                )
            else:
                print("tokens: (provider did not return usage)")
            print("\n==== Prompt ====")
            print(result.prompt)
            print("\n==== Response ====")
            print(result.response_text)
            print("\n==== Commit Message ====")
            print(message)
        else:
            print(message)
        return 0

    if args.debug and result is not None:
        # Also print debug info before commit
        print(f"==== {result.provider} Usage ====")
        print(f"provider: {result.provider}")
        print(f"model: {result.model}")
        print(f"response_id: {result.response_id or '(n/a)'}")
        if result.total_tokens is not None:
            print(
                f"tokens: prompt={result.prompt_tokens} completion={result.completion_tokens} total={result.total_tokens}"
            )
        else:
            print("tokens: (provider did not return usage)")
        print("\n==== Prompt ====")
        print(result.prompt)
        print("\n==== Response ====")
        print(result.response_text)
        print("\n==== Commit Message ====")
        print(message)

    if args.edit:
        rc: int = commit_with_message(message, True, repo_root, amend=args.amend)
    else:
        rc = commit_with_message(message, False, repo_root, amend=args.amend)

    return rc


def main() -> None:
    """Script entry point.

    Parse command-line arguments, delegate to the execution logic, and exit with its code.
    """

    parser: Final[ArgumentParser] = _build_parser()
    args = CliArgs()
    parser.parse_args(namespace=args)

    if args.edit and not args.commit:
        print("'--edit' must be used together with '--commit'.", file=stderr)
        sys_exit(2)

    code: int = _run(args)
    sys_exit(code)
