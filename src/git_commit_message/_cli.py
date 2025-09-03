from __future__ import annotations

"""커맨드라인 인터페이스 엔트리포인트.

레포지토리의 스테이징된 변경사항을 수집하고, OpenAI GPT 모델을 호출해
커밋 메시지를 생성하거나 바로 커밋을 작성합니다.
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
    """CLI 인자 파서를 생성합니다.

    Returns
    -------
    ArgumentParser
        설정이 완료된 인자 파서.
    """

    parser: ArgumentParser = ArgumentParser(
        prog="git-commit-message",
        description=(
            "스테이징된 변경사항을 바탕으로 OpenAI GPT에 의해 커밋 메시지를 생성합니다."
        ),
    )

    parser.add_argument(
        "description",
        nargs="?",
        help="변경 사항에 대한 보조 설명 문자열(선택).",
    )

    parser.add_argument(
        "--commit",
        action="store_true",
        help="생성된 메시지로 즉시 커밋합니다.",
    )

    parser.add_argument(
        "--edit",
        action="store_true",
        help="커밋 전 편집기를 열어 메시지를 수정합니다. '--commit'과 함께 사용하세요.",
    )

    parser.add_argument(
        "--model",
        default=None,
        help=(
            "사용할 OpenAI 모델 이름. 미지정 시 환경변수(GIT_COMMIT_MESSAGE_MODEL, OPENAI_MODEL) 또는 'gpt-5-mini'를 사용합니다."
        ),
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="요청/응답과 토큰 사용량을 출력합니다.",
    )

    return parser


def _run(
    *,
    args: Namespace,
) -> int:
    """메인 실행 로직.

    Parameters
    ----------
    args
        파싱된 CLI 인자.

    Returns
    -------
    int
        프로세스 종료 코드. 0은 성공, 그 외는 실패.
    """

    repo_root: Path = get_repo_root()

    if not has_staged_changes(cwd=repo_root):
        print("스테이징된 변경 사항이 없습니다. 'git add' 후 다시 시도하세요.", file=sys.stderr)
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
            )
            message = result.message
        else:
            message = generate_commit_message(
                diff=diff_text,
                hint=hint,
                model=args.model,
            )
    except Exception as exc:  # noqa: BLE001 - 표준 출력 메시지 유지 목적
        print(f"커밋 메시지 생성 실패: {exc}", file=sys.stderr)
        return 3

    if not args.commit:
        if args.debug and result is not None:
            # 디버그 정보 출력
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
        # 커밋 전에도 디버그 출력
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
    """스크립트 엔트리포인트.

    명령행 인자를 파싱한 후, 실행 로직을 위임하고 종료 코드를 반환합니다.
    """

    parser: Final[ArgumentParser] = _build_parser()
    args: Namespace = parser.parse_args()

    if args.edit and not args.commit:
        print("'--edit'는 '--commit'과 함께 사용해야 합니다.", file=sys.stderr)
        sys.exit(2)

    code: int = _run(args=args)
    sys.exit(code)
