# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Merge the attack score and attribution heads.

Revision ID: c7e9a1b3d5f6
Revises: 2f8c4d6a9b1e, a4c6e8f0b2d1
Create Date: 2026-09-11 09:30:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c7e9a1b3d5f6"
down_revision: str | Sequence[str] | None = ("2f8c4d6a9b1e", "a4c6e8f0b2d1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this schema upgrade."""


def downgrade() -> None:
    """Revert this schema upgrade."""
