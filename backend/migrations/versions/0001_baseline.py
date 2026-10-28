"""Baseline: establishes the migration chain.

No tables yet. Schema arrives with the persistence milestone.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-28

"""

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Nothing to create in the baseline revision."""


def downgrade() -> None:
    """Nothing to remove in the baseline revision."""
