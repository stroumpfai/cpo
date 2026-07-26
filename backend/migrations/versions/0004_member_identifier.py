"""CPO-selectable member identifier on the public ordering form

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No batch rebuild here: SQLite's native ALTER TABLE ADD COLUMN accepts
    # NOT NULL when a non-null DEFAULT is supplied, and no constraint or
    # foreign key is involved (which is what forced batch mode in 0002/0003).
    # Rebuilding via copy_from would mean re-declaring the three UNIQUE
    # constraints on cpos by hand, and the metadata parity test does not
    # inspect unique constraints — a typo there would be silent and permanent.
    op.add_column(
        "cpos",
        sa.Column("member_identifier", sa.Text(), nullable=False, server_default="name"),
    )


def downgrade() -> None:
    # SQLite >= 3.35 supports native DROP COLUMN and keeps the remaining
    # UNIQUE constraints intact.
    op.drop_column("cpos", "member_identifier")
