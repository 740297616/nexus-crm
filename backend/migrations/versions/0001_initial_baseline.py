"""Create the empty Phase 0 database baseline.

Revision ID: 0001_initial_baseline
Revises:
Create Date: 2026-11-14
"""

from collections.abc import Sequence

revision: str = "0001_initial_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish the baseline; business tables are added in later phases."""


def downgrade() -> None:
    """Return to the empty database before the baseline."""
