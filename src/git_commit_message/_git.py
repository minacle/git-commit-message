"""Git-related helper functions.

Provides repository root discovery, extraction of staged changes, and
creating commits from a message.
"""

from __future__ import annotations

from pathlib import Path
from subprocess import CalledProcessError, check_call, check_output, run


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


def get_current_branch(
    cwd: Path,
    /,
) -> str | None:
    """Return the current branch name, or ``None`` if HEAD is detached.

    Parameters
    ----------
    cwd
        Repository directory in which to run Git.

    Returns
    -------
    str | None
        Branch name, or ``None`` when HEAD is detached or the command fails.
    """

    completed = run(
        ["git", "branch", "--show-current"],
        cwd=str(cwd),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        return None
    name = completed.stdout.decode().strip()
    return name or None


def get_git_log(
    cwd: Path,
    /,
    *,
    count: int = 10,
) -> str | None:
    """Return recent Git log entries as formatted text.

    Parameters
    ----------
    cwd
        Repository directory in which to run Git.
    count
        Maximum number of commits to include.

    Returns
    -------
    str | None
        Formatted log text, or ``None`` if the repository has no commits.
    """

    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}")

    if not has_head_commit(cwd):
        return None

    try:
        out: bytes = check_output(
            [
                "git",
                "log",
                f"-{count}",
                "--format=%h %s%n%n%b%n---",
            ],
            cwd=str(cwd),
        )
    except CalledProcessError:
        return None

    text = out.decode().strip()
    return text or None


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
