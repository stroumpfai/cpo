"""Per-team default grace period for new sessions

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-06

"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preselects the "new session" form's grace period stepper; 2 matches the
    # value every existing team already got from the previously-hardcoded
    # frontend default, so no team's behavior changes on upgrade.
    op.add_column(
        "teams",
        sa.Column("default_grace_period_minutes", sa.Integer(), nullable=False, server_default="2"),
    )


def downgrade() -> None:
    op.drop_column("teams", "default_grace_period_minutes")
