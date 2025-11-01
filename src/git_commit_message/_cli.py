from __future__ import annotations

"""Command-line interface entry point.

Collect staged changes from the repository and call an OpenAI GPT model
to generate a commit message, or create a commit straight away.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path
import sys
from typing import Final

from ._git import commit_with_message, get_repo_root, get_staged_diff, has_staged_changes
from ._gpt import (
    generate_commit_message,
    generate_commit_message_with_info,
    CommitMessageResult,
)


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
            "Generate a commit message with OpenAI GPT based on the staged changes."
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
        "--edit",
        action="store_true",
        help="Open an editor to amend the message before committing. Use with '--commit'.",
    )

    parser.add_argument(
        "--model",
        default=None,
        help=(
            "OpenAI model name to use. If unspecified, uses the environment variables (GIT_COMMIT_MESSAGE_MODEL, OPENAI_MODEL) or 'gpt-5-mini'."
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

    return parser


def _run(
    *,
    args: Namespace,
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

    repo_root: Path = get_repo_root()

    if not has_staged_changes(cwd=repo_root):
        print("No staged changes. Run 'git add' and try again.", file=sys.stderr)
        return 2

    diff_text: str = get_staged_diff(cwd=repo_root)

    hint: str | None = args.description if isinstance(args.description, str) else None

    result: CommitMessageResult | None = None
    try:
        if args.debug:
            result = generate_commit_message_with_info(
                diff=diff_text,
                hint=hint,
                model=args.model,
                single_line=getattr(args, "one_line", False),
                subject_max=getattr(args, "max_length", None),
                language=getattr(args, "language", None),
            )
            message = result.message
        else:
            message = generate_commit_message(
                diff=diff_text,
                hint=hint,
                model=args.model,
                single_line=getattr(args, "one_line", False),
                subject_max=getattr(args, "max_length", None),
                language=getattr(args, "language", None),
            )
    except Exception as exc:  # noqa: BLE001 - to preserve standard output messaging
        print(f"Failed to generate commit message: {exc}", file=sys.stderr)
        return 3

    # Option: force single-line message
    if getattr(args, "one_line", False):
        # Use the first non-empty line only
        for line in (ln.strip() for ln in message.splitlines()):
            if line:
                message = line
                break
        else:
            message = ""

    if not args.commit:
        if args.debug and result is not None:
            # Print debug information
            print("==== OpenAI Usage ====")
            print(f"model: {result.model}")
            print(f"response_id: {getattr(result, 'response_id', '(n/a)')}")
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
        print("==== OpenAI Usage ====")
        print(f"model: {result.model}")
        print(f"response_id: {getattr(result, 'response_id', '(n/a)')}")
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
        rc: int = commit_with_message(message=message, edit=True, cwd=repo_root)
    else:
        rc = commit_with_message(message=message, edit=False, cwd=repo_root)

    return rc


def main() -> None:
    """Script entry point.

    Parse command-line arguments, delegate to the execution logic, and exit with its code.
    """

    parser: Final[ArgumentParser] = _build_parser()
    args: Namespace = parser.parse_args()

    if args.edit and not args.commit:
        print("'--edit' must be used together with '--commit'.", file=sys.stderr)
        sys.exit(2)

    code: int = _run(args=args)
    sys.exit(code)
