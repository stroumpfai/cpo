"""Per-login UI language preference

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable, no default and no backfill: NULL means "no explicit choice —
    # follow the browser", which is exactly how every existing account should
    # behave. The column lives on the login rows, not on teams: two CPOs
    # sharing a team can read the app in different languages.
    op.add_column("cpos", sa.Column("language", sa.Text(), nullable=True))
    op.add_column("admins", sa.Column("language", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("admins", "language")
    op.drop_column("cpos", "language")
