"""Public package API for git-commit-message.

Exports:
    - main: CLI entry point
    - OpenAI helpers: generate_commit_message_openai / generate_commit_message_with_info_openai
    - Gemini helpers: generate_commit_message_gemini / generate_commit_message_with_info_gemini

Provider-specific functions mirror the original names while making future routing simpler.
"""

from ._cli import main
from ._gpt import generate_commit_message as generate_commit_message_openai
from ._gpt import generate_commit_message_with_info as generate_commit_message_with_info_openai
from ._gemini import generate_commit_message as generate_commit_message_gemini
from ._gemini import generate_commit_message_with_info as generate_commit_message_with_info_gemini

__all__ = (
        "main",
        "generate_commit_message_openai",
        "generate_commit_message_with_info_openai",
        "generate_commit_message_gemini",
        "generate_commit_message_with_info_gemini",
)
