"""Git-related helper functions.

Provides repository root discovery, extraction of staged changes, and
creating commits from a message.
"""

from __future__ import annotations

from os import chmod, environ
from pathlib import Path
from subprocess import CalledProcessError, check_call, check_output, run
from tempfile import TemporaryDirectory


def _get_empty_tree_hash(
    cwd: Path,
    /,
) -> str:
    """Return the empty tree hash for this repository.

    Parameters
    ----------
    cwd
        Repository directory in which to run Git.

    Notes
    -----
    Do not hard-code the SHA, because repositories may use different
    hash algorithms (e.g. SHA-1 vs SHA-256). We ask Git to compute the
    empty tree object ID for the current repo.

    Returns
    -------
    str
        The empty tree object ID for the current repository.
    """

    try:
        completed = run(
            [
                "git",
                "hash-object",
                "-t",
                "tree",
                "--stdin",
            ],
            cwd=str(cwd),
            check=True,
            input=b"",
            capture_output=True,
        )
    except CalledProcessError as exc:
        stderr_text = (exc.stderr or b"").decode(errors="replace").strip()
        suffix = f"\nGit stderr: {stderr_text}" if stderr_text else ""
        raise RuntimeError(
            f"Failed to compute empty tree hash (git exited with {exc.returncode}).{suffix}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Failed to run git to compute empty tree hash: {exc}"
        ) from exc
    oid = completed.stdout.decode().strip()
    if not oid:
        raise RuntimeError(
            "Failed to compute empty tree hash: git returned an empty object ID."
        )
    return oid


def get_repo_root(
    cwd: Path | None = None,
    /,
) -> Path:
    """Find the repository root from the current working directory.

    Parameters
    ----------
    cwd
        Starting directory for the search. Defaults to the current working directory.

    Returns
    -------
    Path
        The repository root path.
    """

    start: Path = cwd or Path.cwd()
    try:
        out: bytes = check_output(
            [
                "git",
                "rev-parse",
                "--show-toplevel",
            ],
            cwd=str(start),
        )
    except CalledProcessError as exc:  # noqa: TRY003
        raise RuntimeError("Not a Git repository.") from exc

    root = Path(out.decode().strip())
    return root


def has_staged_changes(
    cwd: Path,
    /,
) -> bool:
    """Check whether there are staged changes."""

    try:
        check_call(
            ["git", "diff", "--cached", "--quiet", "--exit-code"],
            cwd=str(cwd),
        )
        return False
    except CalledProcessError:
        return True


def has_head_commit(
    cwd: Path,
    /,
) -> bool:
    """Return True if the repository has at least one commit (HEAD exists).

    Parameters
    ----------
    cwd
        Repository directory in which to run Git.

    Returns
    -------
    bool
        True if ``HEAD`` exists in the repository, False otherwise.
    """

    completed = run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=str(cwd),
        check=False,
        capture_output=True,
    )
    return completed.returncode == 0


def resolve_amend_base_ref(
    cwd: Path,
    /,
) -> str:
    """Resolve the base ref for an amend diff.

    Parameters
    ----------
    cwd
        Repository directory in which to run Git.

    Notes
    -----
    The amended commit keeps the same parent as the current HEAD commit.

    - If HEAD has a parent, base is ``HEAD^``.
    - If HEAD is a root commit (no parent), base is the empty tree.

    Returns
    -------
    str
        The base reference for the amend diff: either ``HEAD^`` (when the
        current ``HEAD`` commit has a parent) or the empty tree object ID
        (when ``HEAD`` is a root commit).
    """

    completed = run(
        ["git", "rev-parse", "--verify", "HEAD^"],
        cwd=str(cwd),
        check=False,
        capture_output=True,
    )
    if completed.returncode == 0:
        return "HEAD^"
    return _get_empty_tree_hash(cwd)


def resolve_commit_ref(
    cwd: Path,
    ref: str,
    /,
) -> str:
    """Resolve an arbitrary ref into a commit hash.

    Parameters
    ----------
    cwd
        Repository directory in which to run Git.
    ref
        Any commit-ish reference accepted by Git.

    Returns
    -------
    str
        Full commit hash for the given reference.
    """

    completed = run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=str(cwd),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        stderr_text = completed.stderr.decode(errors="replace").strip()
        suffix = f" Git stderr: {stderr_text}" if stderr_text else ""
        raise RuntimeError(f"Invalid commit reference: {ref}.{suffix}")
    return completed.stdout.decode().strip()


def is_ancestor_commit(
    cwd: Path,
    ancestor: str,
    descendant: str = "HEAD",
    /,
) -> bool:
    """Return True if ``ancestor`` is reachable from ``descendant``."""

    completed = run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=str(cwd),
        check=False,
        capture_output=True,
    )
    return completed.returncode == 0


def get_commit_diff(
    cwd: Path,
    ref: str,
    /,
    *,
    context_lines: int | None = None,
) -> str:
    """Return patch text for a specific commit.

    Parameters
    ----------
    cwd
        Git working directory.
    ref
        Commit reference to inspect.
    context_lines
        Optional number of context lines for unified diff output. When ``None``,
        Git's default context lines are used.

    Returns
    -------
    str
        Unified diff text for the specified commit.
    """

    commit_hash = resolve_commit_ref(cwd, ref)
    cmd: list[str] = [
        "git",
        "show",
        "--patch",
        "--minimal",
        "--no-color",
        "--format=",
    ]
    if context_lines is not None:
        cmd.append(f"-U{context_lines}")
    cmd.append(commit_hash)

    try:
        out: bytes = check_output(cmd, cwd=str(cwd))
    except CalledProcessError as exc:
        raise RuntimeError(
            "Failed to retrieve diff for the specified commit."
        ) from exc

    return out.decode()


def _resolve_reword_upstream(
    cwd: Path,
    commit_hash: str,
    /,
) -> tuple[list[str], bool]:
    """Resolve the upstream argument for interactive rebase.

    Returns
    -------
    tuple[list[str], bool]
        Rebase argument list and whether the target is a root commit.
    """

    parent = run(
        ["git", "rev-parse", "--verify", f"{commit_hash}^"],
        cwd=str(cwd),
        check=False,
        capture_output=True,
    )
    if parent.returncode == 0:
        upstream = parent.stdout.decode().strip()
        return ["-i", upstream], False
    return ["-i", "--root"], True


def reword_commit_with_message(
    message: str,
    commit_hash: str,
    cwd: Path,
    /,
) -> int:
    """Reword a specific commit via non-interactive interactive rebase.

    Parameters
    ----------
    message
        Commit message to apply to the target commit.
    commit_hash
        Full hash of the target commit.
    cwd
        Git working directory.

    Returns
    -------
    int
        The subprocess exit code.
    """

    rebase_args, _ = _resolve_reword_upstream(cwd, commit_hash)

    with TemporaryDirectory(prefix="git-commit-message-reword-") as temp_dir:
        temp_path = Path(temp_dir)
        message_file = temp_path / "message.txt"
        sequence_editor = temp_path / "sequence-editor.sh"
        commit_editor = temp_path / "commit-editor.sh"

        message_file.write_text(message.rstrip() + "\n", encoding="utf-8")

        sequence_editor.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "todo_file=\"$1\"\n"
            f"target_hash=\"{commit_hash}\"\n"
            "awk -v target=\"$target_hash\" '\n"
            "BEGIN { found = 0 }\n"
            "{\n"
            "  if ($1 == \"pick\" && $2 == target) {\n"
            "    $1 = \"reword\"\n"
            "    found = 1\n"
            "  }\n"
            "  print\n"
            "}\n"
            "END {\n"
            "  if (!found) {\n"
            "    print \"Failed to mark target commit for reword during rebase.\" > \"/dev/stderr\"\n"
            "    exit 3\n"
            "  }\n"
            "}\n"
            "' \"$todo_file\" > \"$todo_file.tmp\"\n"
            "mv \"$todo_file.tmp\" \"$todo_file\"\n",
            encoding="utf-8",
        )

        commit_editor.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "target_file=\"$1\"\n"
            f"cat \"{message_file}\" > \"$target_file\"\n",
            encoding="utf-8",
        )

        chmod(sequence_editor, 0o700)
        chmod(commit_editor, 0o700)

        env = dict(environ)
        env["GIT_SEQUENCE_EDITOR"] = str(sequence_editor)
        env["GIT_EDITOR"] = str(commit_editor)

        completed = run(
            ["git", "rebase", *rebase_args],
            cwd=str(cwd),
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            run(["git", "rebase", "--abort"], cwd=str(cwd), check=False)
        return int(completed.returncode)


def get_staged_diff(
    cwd: Path,
    /,
    *,
    base_ref: str | None = None,
    context_lines: int | None = None,
) -> str:
    """Return the staged changes as diff text.

    Parameters
    ----------
    cwd
        Git working directory.
    base_ref
        Optional Git reference or tree object ID (e.g., branch name, tag,
        commit hash, or the empty tree hash) to diff against. When provided,
        the diff shows changes from ``base_ref`` to the staged index, instead
        of changes from ``HEAD`` to the staged index.
    context_lines
        Optional number of context lines for unified diff output. When ``None``,
        Git's default context lines are used.

    Returns
    -------
    str
        Unified diff text for the staged changes.
    """

    cmd: list[str] = [
        "git",
        "diff",
        "--cached",
        "--patch",
        "--minimal",
        "--no-color",
    ]
    if context_lines is not None:
        cmd.append(f"-U{context_lines}")
    if base_ref:
        cmd.append(base_ref)

    try:
        out: bytes = check_output(cmd, cwd=str(cwd))
    except CalledProcessError as exc:
        message = "Failed to retrieve staged diff from Git."
        if base_ref:
            message += (
                " Ensure that the provided base_ref exists and is a valid Git reference."
            )
        raise RuntimeError(message) from exc

    return out.decode()


def commit_with_message(
    message: str,
    edit: bool,
    cwd: Path,
    /,
    *,
    amend: bool = False,
) -> int:
    """Create a commit with the given message.

    Parameters
    ----------
    message
        Commit message.
    edit
        If True, use the `--edit` flag to open an editor for amendments.
    cwd
        Git working directory.
    amend
        If True, pass ``--amend`` to Git to amend the current ``HEAD`` commit
        instead of creating a new commit.

    Returns
    -------
    int
        The subprocess exit code.
    """

    cmd: list[str] = ["git", "commit"]
    if amend:
        cmd.append("--amend")

    cmd.extend(["-m", message])
    if edit:
        cmd.append("--edit")

    try:
        completed = run(cmd, cwd=str(cwd), check=False)
        return int(completed.returncode)
    except OSError as exc:  # e.g., editor launch failure, etc.
        raise RuntimeError(f"Failed to run 'git commit': {exc}") from exc
