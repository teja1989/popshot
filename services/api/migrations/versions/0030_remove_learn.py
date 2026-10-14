"""Remove Learn shots (0029): the feature was dropped before anything was published.

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-14

Drops the shots table, its functions and the 'learn.public' switch. Any admin_actions rows
about shots stay, as a record. Downgrading puts 0029 back as it was, empty.
"""

import importlib.util
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _learn() -> ModuleType:
    """Migration 0029 itself, whose file name can't be imported the usual way."""
    spec = importlib.util.spec_from_file_location(
        "learn_0029", Path(__file__).with_name("0029_learn.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Migration 0029 is missing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upgrade() -> None:
    _learn().downgrade()


def downgrade() -> None:
    _learn().upgrade()
