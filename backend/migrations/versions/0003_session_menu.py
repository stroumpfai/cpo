"""Multi-menu support: sessions reference the menu they serve

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# SQLite cannot ALTER-add a foreign key, so batch mode rebuilds the table.
# copy_from describes the current table explicitly (check-constraint
# reflection is unreliable) so the rebuild keeps the constraint and index.
_sessions_v1 = sa.Table(
    "sessions",
    sa.MetaData(),
    sa.Column("id", sa.Text(), primary_key=True),
    sa.Column("cpo_id", sa.Text(), sa.ForeignKey("cpos.id", ondelete="CASCADE"), nullable=False),
    sa.Column("team_name", sa.Text(), nullable=False),
    sa.Column("session_date", sa.Text(), nullable=False),
    sa.Column("start_time", sa.Text(), nullable=False),
    sa.Column("end_time", sa.Text(), nullable=False),
    sa.Column("grace_period_minutes", sa.Integer(), nullable=False, server_default="2"),
    sa.Column("created_at", sa.Text(), nullable=False),
    sa.Column("closed_at", sa.Text(), nullable=True),
    sa.CheckConstraint("grace_period_minutes >= 0", name="ck_sessions_grace_min"),
    sa.Index("ix_sessions_cpo_created", "cpo_id", "created_at"),
)


def upgrade() -> None:
    with op.batch_alter_table("sessions", copy_from=_sessions_v1) as batch:
        batch.add_column(sa.Column("menu_id", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_sessions_menu", "menus", ["menu_id"], ["id"], ondelete="SET NULL"
        )
    # Existing sessions were all served from the CPO's single default menu.
    op.execute(
        "UPDATE sessions SET menu_id = "
        "(SELECT m.id FROM menus m WHERE m.cpo_id = sessions.cpo_id AND m.is_default = 1)"
    )


def downgrade() -> None:
    sessions_v2 = sa.Table(
        "sessions",
        sa.MetaData(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("cpo_id", sa.Text(), sa.ForeignKey("cpos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_name", sa.Text(), nullable=False),
        sa.Column("session_date", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Text(), nullable=False),
        sa.Column("end_time", sa.Text(), nullable=False),
        sa.Column("grace_period_minutes", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("closed_at", sa.Text(), nullable=True),
        sa.Column("menu_id", sa.Text(), sa.ForeignKey("menus.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("grace_period_minutes >= 0", name="ck_sessions_grace_min"),
        sa.Index("ix_sessions_cpo_created", "cpo_id", "created_at"),
    )
    with op.batch_alter_table("sessions", copy_from=sessions_v2) as batch:
        batch.drop_column("menu_id")
