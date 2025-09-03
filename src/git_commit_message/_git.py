from __future__ import annotations

"""Git 관련 헬퍼 함수들.

레포 루트 탐색, 스테이징된 변경사항 추출, 메시지로 커밋 생성 등을 제공합니다.
"""

from pathlib import Path
import subprocess


def get_repo_root(
    *,
    cwd: Path | None = None,
) -> Path:
    """현재 작업 디렉토리에서 레포지토리 루트를 찾습니다.

    Parameters
    ----------
    cwd
        탐색 시작 디렉토리. 기본값은 현재 작업 디렉토리.

    Returns
    -------
    Path
        레포지토리 루트 경로.
    """

    start: Path = cwd or Path.cwd()
    try:
        out: bytes = subprocess.check_output(
            [
                "git",
                "rev-parse",
                "--show-toplevel",
            ],
            cwd=str(start),
        )
    except subprocess.CalledProcessError as exc:  # noqa: TRY003
        raise RuntimeError("Git 레포지토리가 아닙니다.") from exc

    root = Path(out.decode().strip())
    return root


def has_staged_changes(
    *,
    cwd: Path,
) -> bool:
    """스테이징된 변경사항 유무를 확인합니다."""

    try:
        subprocess.check_call(
            ["git", "diff", "--cached", "--quiet", "--exit-code"],
            cwd=str(cwd),
        )
        return False
    except subprocess.CalledProcessError:
        return True


def get_staged_diff(
    *,
    cwd: Path,
) -> str:
    """스테이징된 변경사항을 diff 텍스트로 반환합니다."""

    out: bytes = subprocess.check_output(
        [
            "git",
            "diff",
            "--cached",
            "--patch",
            "--minimal",
            "--no-color",
        ],
        cwd=str(cwd),
    )
    return out.decode()


def commit_with_message(
    *,
    message: str,
    edit: bool,
    cwd: Path,
) -> int:
    """주어진 메시지로 커밋을 생성합니다.

    Parameters
    ----------
    message
        커밋 메시지.
    edit
        True면 편집기를 열어 수정하도록 `--edit` 플래그를 사용합니다.
    cwd
        Git 작업 디렉토리.

    Returns
    -------
    int
        하위 프로세스의 종료 코드.
    """

    cmd: list[str] = ["git", "commit", "-m", message]
    if edit:
        cmd.append("--edit")

    try:
        completed = subprocess.run(cmd, cwd=str(cwd), check=False)
        return int(completed.returncode)
    except OSError as exc:  # 예: 편집기 실행 실패 등
        raise RuntimeError(f"git commit 실행 실패: {exc}") from exc
