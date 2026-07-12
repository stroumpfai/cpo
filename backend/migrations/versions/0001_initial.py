"""Initial schema: admins, cpos, menus, pizzas, sessions, orders

Revision ID: 0001
Revises:
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_admins_single_row"),
    )
    op.create_table(
        "cpos",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("team_name", sa.Text(), nullable=False),
        sa.Column("unique_link", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.Text(), nullable=False, server_default="CHF"),
    )
    op.create_table(
        "menus",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "cpo_id",
            sa.Text(),
            sa.ForeignKey("cpos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False, server_default="Default"),
        sa.Column("is_default", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pizzeria_url", sa.Text(), nullable=True),
    )
    op.create_index(
        "ux_menus_one_default",
        "menus",
        ["cpo_id"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )
    op.create_table(
        "pizzas",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "menu_id",
            sa.Text(),
            sa.ForeignKey("menus.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.CheckConstraint("price >= 0.01", name="ck_pizzas_price_min"),
    )
    op.create_index("ix_pizzas_menu", "pizzas", ["menu_id"])
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "cpo_id",
            sa.Text(),
            sa.ForeignKey("cpos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("team_name", sa.Text(), nullable=False),
        sa.Column("session_date", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Text(), nullable=False),
        sa.Column("end_time", sa.Text(), nullable=False),
        sa.Column("grace_period_minutes", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("closed_at", sa.Text(), nullable=True),
        sa.CheckConstraint("grace_period_minutes >= 0", name="ck_sessions_grace_min"),
    )
    op.create_index("ix_sessions_cpo_created", "sessions", ["cpo_id", "created_at"])
    op.create_table(
        "orders",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Text(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("member_name", sa.Text(), nullable=False),
        sa.Column("pizza_id", sa.Text(), nullable=False),
        sa.Column("pizza_name", sa.Text(), nullable=False),
        sa.Column("pizza_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_price", sa.Float(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("client_ip", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("received", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("quantity >= 1", name="ck_orders_quantity_min"),
    )
    op.create_index("ix_orders_session", "orders", ["session_id"])


def downgrade() -> None:
    op.drop_table("orders")
    op.drop_table("sessions")
    op.drop_table("pizzas")
    op.drop_table("menus")
    op.drop_table("cpos")
    op.drop_table("admins")
