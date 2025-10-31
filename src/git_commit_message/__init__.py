"""Public package exporting the CLI and internal utilities.

This module exposes only public symbols in accordance with the codestyle guide.
"""

from ._cli import main

__all__ = (
    "main",
)
