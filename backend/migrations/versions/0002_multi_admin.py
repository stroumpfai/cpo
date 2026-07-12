"""Multi-admin support: drop single-row constraint, add token_version, unique username

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# SQLite cannot ALTER constraints, so batch mode rebuilds the table. copy_from
# describes the current table explicitly (without ck_admins_single_row) because
# SQLite check-constraint reflection is unreliable; the rebuild drops it.
_admins_v1 = sa.Table(
    "admins",
    sa.MetaData(),
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("username", sa.Text(), nullable=False),
    sa.Column("password_hash", sa.Text(), nullable=False),
    sa.Column("created_at", sa.Text(), nullable=False),
)


def upgrade() -> None:
    with op.batch_alter_table("admins", copy_from=_admins_v1) as batch:
        batch.add_column(
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_unique_constraint("uq_admins_username", ["username"])


def downgrade() -> None:
    admins_v2 = sa.Table(
        "admins",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("username", name="uq_admins_username"),
    )
    # Lossy for extra admin rows: keep only the lowest id so the restored
    # single-row constraint holds.
    op.execute("DELETE FROM admins WHERE id != (SELECT MIN(id) FROM admins)")
    op.execute("UPDATE admins SET id = 1")
    with op.batch_alter_table("admins", copy_from=admins_v2) as batch:
        batch.drop_constraint("uq_admins_username", type_="unique")
        batch.drop_column("token_version")
        batch.create_check_constraint("ck_admins_single_row", "id = 1")
