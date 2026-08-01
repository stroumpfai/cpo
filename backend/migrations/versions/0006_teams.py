"""Multi-CPO teams: split team identity out of the CPO login row

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# SQLite cannot ALTER-add a foreign key or drop a column with one, so batch
# mode rebuilds each table. copy_from describes the table's current shape
# explicitly (check-constraint reflection is unreliable) — see 0002/0003 for
# the same pattern. Every table is migrated in two batch passes: add the new
# nullable column, backfill it, then finalize (NOT NULL + FK + drop old
# columns) — SQLite can't add a NOT NULL column with a FK in one step when
# existing rows need a computed value first.

_cpos_v5 = sa.Table(
    "cpos", sa.MetaData(),
    sa.Column("id", sa.Text(), primary_key=True),
    sa.Column("username", sa.Text(), nullable=False, unique=True),
    sa.Column("email", sa.Text(), nullable=False, unique=True),
    sa.Column("password_hash", sa.Text(), nullable=False),
    sa.Column("team_name", sa.Text(), nullable=False),
    sa.Column("unique_link", sa.Text(), nullable=False, unique=True),
    sa.Column("created_at", sa.Text(), nullable=False),
    sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("currency", sa.Text(), nullable=False, server_default="CHF"),
    sa.Column("member_identifier", sa.Text(), nullable=False, server_default="name"),
    sa.Column("stats_reset_at", sa.Text(), nullable=True),
)

_cpos_v5_with_team_id = sa.Table(
    "cpos", sa.MetaData(),
    sa.Column("id", sa.Text(), primary_key=True),
    sa.Column("username", sa.Text(), nullable=False, unique=True),
    sa.Column("email", sa.Text(), nullable=False, unique=True),
    sa.Column("password_hash", sa.Text(), nullable=False),
    sa.Column("team_name", sa.Text(), nullable=False),
    sa.Column("unique_link", sa.Text(), nullable=False, unique=True),
    sa.Column("created_at", sa.Text(), nullable=False),
    sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("currency", sa.Text(), nullable=False, server_default="CHF"),
    sa.Column("member_identifier", sa.Text(), nullable=False, server_default="name"),
    sa.Column("stats_reset_at", sa.Text(), nullable=True),
    sa.Column("team_id", sa.Text(), nullable=True),
)

_menus_v5 = sa.Table(
    "menus", sa.MetaData(),
    sa.Column("id", sa.Text(), primary_key=True),
    sa.Column("cpo_id", sa.Text(), sa.ForeignKey("cpos.id", ondelete="CASCADE"), nullable=False),
    sa.Column("name", sa.Text(), nullable=False, server_default="Default"),
    sa.Column("is_default", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("pizzeria_url", sa.Text(), nullable=True),
)

_menus_v5_with_team_id = sa.Table(
    "menus", sa.MetaData(),
    sa.Column("id", sa.Text(), primary_key=True),
    sa.Column("cpo_id", sa.Text(), sa.ForeignKey("cpos.id", ondelete="CASCADE"), nullable=False),
    sa.Column("name", sa.Text(), nullable=False, server_default="Default"),
    sa.Column("is_default", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("pizzeria_url", sa.Text(), nullable=True),
    sa.Column("team_id", sa.Text(), nullable=True),
)

_sessions_v5 = sa.Table(
    "sessions", sa.MetaData(),
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
)

_sessions_v5_with_team_id = sa.Table(
    "sessions", sa.MetaData(),
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
    sa.Column("team_id", sa.Text(), nullable=True),
    sa.CheckConstraint("grace_period_minutes >= 0", name="ck_sessions_grace_min"),
)


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("team_name", sa.Text(), nullable=False),
        sa.Column("unique_link", sa.Text(), nullable=False, unique=True),
        sa.Column("currency", sa.Text(), nullable=False, server_default="CHF"),
        sa.Column("member_identifier", sa.Text(), nullable=False, server_default="name"),
        sa.Column("stats_reset_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    # Every existing CPO row becomes its own team, reusing its own id as the
    # team's id — that makes the menus/sessions backfill below a same-value
    # copy (cpo_id already equals the right team_id) instead of a join.
    op.execute(
        "INSERT INTO teams (id, team_name, unique_link, currency, member_identifier, "
        "stats_reset_at, created_at) "
        "SELECT id, team_name, unique_link, currency, member_identifier, "
        "stats_reset_at, created_at FROM cpos"
    )

    with op.batch_alter_table("cpos", copy_from=_cpos_v5) as batch:
        batch.add_column(sa.Column("team_id", sa.Text(), nullable=True))
    op.execute("UPDATE cpos SET team_id = id")
    with op.batch_alter_table("cpos", copy_from=_cpos_v5_with_team_id) as batch:
        batch.alter_column("team_id", nullable=False)
        batch.create_foreign_key(
            "fk_cpos_team_id_teams", "teams", ["team_id"], ["id"], ondelete="CASCADE"
        )
        batch.drop_column("team_name")
        batch.drop_column("unique_link")
        batch.drop_column("currency")
        batch.drop_column("member_identifier")
        batch.drop_column("stats_reset_at")

    with op.batch_alter_table("menus", copy_from=_menus_v5) as batch:
        batch.add_column(sa.Column("team_id", sa.Text(), nullable=True))
    op.execute("UPDATE menus SET team_id = cpo_id")
    with op.batch_alter_table("menus", copy_from=_menus_v5_with_team_id) as batch:
        batch.alter_column("team_id", nullable=False)
        batch.create_foreign_key(
            "fk_menus_team_id_teams", "teams", ["team_id"], ["id"], ondelete="CASCADE"
        )
        batch.drop_column("cpo_id")
    # The old ux_menus_one_default index (on cpo_id) was dropped along with
    # the table it lived on during the batch recreate above; re-add it here
    # scoped to the new column so "one default menu per team" still holds.
    op.create_index(
        "ux_menus_one_default", "menus", ["team_id"],
        unique=True, sqlite_where=sa.text("is_default = 1"),
    )

    with op.batch_alter_table("sessions", copy_from=_sessions_v5) as batch:
        batch.add_column(sa.Column("team_id", sa.Text(), nullable=True))
    op.execute("UPDATE sessions SET team_id = cpo_id")
    with op.batch_alter_table("sessions", copy_from=_sessions_v5_with_team_id) as batch:
        batch.alter_column("team_id", nullable=False)
        batch.create_foreign_key(
            "fk_sessions_team_id_teams", "teams", ["team_id"], ["id"], ondelete="CASCADE"
        )
        batch.drop_column("cpo_id")
    op.create_index("ix_sessions_team_created", "sessions", ["team_id", "created_at"])

    op.create_table(
        "team_invites",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("team_id", sa.Text(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column("created_by_cpo_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("used_at", sa.Text(), nullable=True),
    )
    op.create_index("ix_team_invites_team", "team_invites", ["team_id"])


def downgrade() -> None:
    # Lossy, like 0002's admin downgrade: a team can hold several CPO logins
    # now, but "one CPO row = one team" only has room for one. Keep the
    # earliest-created login per team (arbitrary but deterministic) and drop
    # the rest — their sessions/menus/orders belonged to the team, not to
    # any one login, so nothing else needs to move.
    op.execute(
        "DELETE FROM cpos WHERE id NOT IN ("
        "  SELECT id FROM cpos c1 WHERE created_at = ("
        "    SELECT MIN(c2.created_at) FROM cpos c2 WHERE c2.team_id = c1.team_id"
        "  )"
        ")"
    )

    op.drop_index("ix_team_invites_team", table_name="team_invites")
    op.drop_table("team_invites")

    op.drop_index("ix_sessions_team_created", table_name="sessions")
    with op.batch_alter_table("sessions", copy_from=_sessions_v5_with_team_id) as batch:
        batch.add_column(sa.Column("cpo_id", sa.Text(), nullable=True))
    op.execute("UPDATE sessions SET cpo_id = team_id")
    sessions_v6 = sa.Table(
        "sessions", sa.MetaData(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("team_id", sa.Text(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_name", sa.Text(), nullable=False),
        sa.Column("session_date", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Text(), nullable=False),
        sa.Column("end_time", sa.Text(), nullable=False),
        sa.Column("grace_period_minutes", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("closed_at", sa.Text(), nullable=True),
        sa.Column("menu_id", sa.Text(), sa.ForeignKey("menus.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cpo_id", sa.Text(), nullable=True),
        sa.CheckConstraint("grace_period_minutes >= 0", name="ck_sessions_grace_min"),
    )
    with op.batch_alter_table("sessions", copy_from=sessions_v6) as batch:
        batch.alter_column("cpo_id", nullable=False)
        batch.create_foreign_key(
            "fk_sessions_cpo_id_cpos", "cpos", ["cpo_id"], ["id"], ondelete="CASCADE"
        )
        batch.drop_column("team_id")
    op.create_index("ix_sessions_cpo_created", "sessions", ["cpo_id", "created_at"])

    op.drop_index("ux_menus_one_default", table_name="menus")
    with op.batch_alter_table("menus", copy_from=_menus_v5_with_team_id) as batch:
        batch.add_column(sa.Column("cpo_id", sa.Text(), nullable=True))
    op.execute("UPDATE menus SET cpo_id = team_id")
    menus_v6 = sa.Table(
        "menus", sa.MetaData(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("team_id", sa.Text(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False, server_default="Default"),
        sa.Column("is_default", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pizzeria_url", sa.Text(), nullable=True),
        sa.Column("cpo_id", sa.Text(), nullable=True),
    )
    with op.batch_alter_table("menus", copy_from=menus_v6) as batch:
        batch.alter_column("cpo_id", nullable=False)
        batch.create_foreign_key(
            "fk_menus_cpo_id_cpos", "cpos", ["cpo_id"], ["id"], ondelete="CASCADE"
        )
        batch.drop_column("team_id")
    op.create_index(
        "ux_menus_one_default", "menus", ["cpo_id"],
        unique=True, sqlite_where=sa.text("is_default = 1"),
    )

    cpos_v6 = sa.Table(
        "cpos", sa.MetaData(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("team_id", sa.Text(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    with op.batch_alter_table("cpos", copy_from=cpos_v6) as batch:
        batch.add_column(sa.Column("team_name", sa.Text(), nullable=True))
        batch.add_column(sa.Column("unique_link", sa.Text(), nullable=True))
        batch.add_column(sa.Column("currency", sa.Text(), nullable=False, server_default="CHF"))
        batch.add_column(sa.Column("member_identifier", sa.Text(), nullable=False, server_default="name"))
        batch.add_column(sa.Column("stats_reset_at", sa.Text(), nullable=True))
    op.execute(
        "UPDATE cpos SET "
        "team_name = (SELECT team_name FROM teams WHERE teams.id = cpos.team_id), "
        "unique_link = (SELECT unique_link FROM teams WHERE teams.id = cpos.team_id), "
        "currency = (SELECT currency FROM teams WHERE teams.id = cpos.team_id), "
        "member_identifier = (SELECT member_identifier FROM teams WHERE teams.id = cpos.team_id), "
        "stats_reset_at = (SELECT stats_reset_at FROM teams WHERE teams.id = cpos.team_id)"
    )
    cpos_v6_with_team_cols = sa.Table(
        "cpos", sa.MetaData(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("team_id", sa.Text(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("team_name", sa.Text(), nullable=True),
        sa.Column("unique_link", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=False, server_default="CHF"),
        sa.Column("member_identifier", sa.Text(), nullable=False, server_default="name"),
        sa.Column("stats_reset_at", sa.Text(), nullable=True),
    )
    with op.batch_alter_table("cpos", copy_from=cpos_v6_with_team_cols) as batch:
        batch.alter_column("team_name", nullable=False)
        batch.alter_column("unique_link", nullable=False)
        batch.create_unique_constraint("uq_cpos_unique_link", ["unique_link"])
        batch.drop_column("team_id")

    op.drop_table("teams")
