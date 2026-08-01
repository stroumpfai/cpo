"""
One-time import of the legacy JSON file storage into SQLite.

Runs at every startup but is a no-op once the database holds an admin
account. On the first boot after upgrading, it reads config.json and the
per-CPO data directories, inserts everything in a single transaction, then
archives the JSON files (DATA_DIR/{cpo_id} → DATA_DIR/_migrated_json/{cpo_id},
config.json → config.json.migrated) so the originals survive as a backup.

Any parse or insert error rolls the transaction back, leaves the JSON files
untouched and aborts startup — the app never boots with partial data.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select

import config
import schema as S
from db import get_engine
from models import MenuFile, Order
from utils import new_id

logger = logging.getLogger("uvicorn.error")

ARCHIVE_DIR_NAME = "_migrated_json"


# Legacy config.json shape: a single "admin" object without id/token_version
# (those columns arrived with multi-admin support), and one CPO row per team
# holding what is now split across teams + cpos (team_name/unique_link/
# currency/member_identifier/stats_reset_at live on TeamRecord today). Parsed
# with dedicated models because models.CPORecord no longer carries them.
class _LegacyAdmin(BaseModel):
    username: str
    password_hash: str
    created_at: datetime


class _LegacyCPO(BaseModel):
    id: str
    username: str
    email: str
    password_hash: str
    team_name: str
    unique_link: str
    created_at: datetime
    token_version: int = 0
    currency: str = "CHF"
    member_identifier: Literal["name", "email"] = "name"
    stats_reset_at: datetime | None = None


class _LegacyConfig(BaseModel):
    admin: _LegacyAdmin
    cpos: list[_LegacyCPO] = Field(default_factory=list)


# Legacy {cpo_id}/{session_id}.json shape: "cpo_id" instead of today's
# "team_id" (see SessionFile in models.py).
class _LegacySessionFile(BaseModel):
    id: str
    cpo_id: str
    team_name: str
    session_date: date
    start_time: str
    end_time: str
    grace_period_minutes: int = 2
    created_at: datetime
    closed_at: datetime | None = None
    menu_id: str | None = None
    orders: list[Order] = Field(default_factory=list)


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def migrate_legacy_json_if_needed() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        admin_count = conn.execute(select(func.count()).select_from(S.admins)).scalar()
        if admin_count:
            logger.info("Database already initialized — skipping legacy JSON import")
            return

        if not os.path.exists(config.CONFIG_PATH):
            logger.info(
                "No database content and no legacy config at %s — fresh install",
                config.CONFIG_PATH,
            )
            return

        logger.info("Importing legacy JSON data from %s", config.CONFIG_PATH)
        counts = {"cpos": 0, "menus": 0, "pizzas": 0, "sessions": 0, "orders": 0}
        current_file = config.CONFIG_PATH
        imported_dirs: list[Path] = []
        try:
            cfg = _LegacyConfig.model_validate(_load_json(Path(config.CONFIG_PATH)))
            conn.execute(
                S.admins.insert().values(
                    id=1, token_version=0, **cfg.admin.model_dump(mode="json")
                )
            )
            for cpo in cfg.cpos:
                # Legacy layout was one CPO per team; reuse the CPO's own id
                # as the new team's id, same as Alembic migration 0006.
                data = cpo.model_dump(mode="json")
                conn.execute(S.teams.insert().values(
                    id=cpo.id,
                    team_name=data["team_name"],
                    unique_link=data["unique_link"],
                    currency=data["currency"],
                    member_identifier=data["member_identifier"],
                    stats_reset_at=data["stats_reset_at"],
                    created_at=data["created_at"],
                ))
                conn.execute(S.cpos.insert().values(
                    id=cpo.id,
                    team_id=cpo.id,
                    username=data["username"],
                    email=data["email"],
                    password_hash=data["password_hash"],
                    created_at=data["created_at"],
                    token_version=data["token_version"],
                ))
                counts["cpos"] += 1

                cpo_dir = Path(config.DATA_DIR) / cpo.id
                if not cpo_dir.is_dir():
                    continue
                imported_dirs.append(cpo_dir)

                menu_path = cpo_dir / "menu.json"
                default_menu_id: str | None = None
                if menu_path.exists():
                    current_file = str(menu_path)
                    menu = MenuFile.model_validate(_load_json(menu_path))
                    menu_id = default_menu_id = new_id()
                    conn.execute(
                        S.menus.insert().values(
                            id=menu_id,
                            team_id=cpo.id,
                            pizzeria_url=menu.pizzeria_url,
                        )
                    )
                    counts["menus"] += 1
                    for pizza in menu.pizzas:
                        conn.execute(
                            S.pizzas.insert().values(
                                menu_id=menu_id, **pizza.model_dump(mode="json")
                            )
                        )
                        counts["pizzas"] += 1

                for session_path in sorted(cpo_dir.glob("*.json")):
                    if session_path.name == "menu.json":
                        continue
                    current_file = str(session_path)
                    # Pydantic supplies defaults for fields missing in old
                    # files (order comment/received/quantity).
                    session = _LegacySessionFile.model_validate(_load_json(session_path))
                    session_data = session.model_dump(mode="json")
                    order_dicts = session_data.pop("orders")
                    session_data["team_id"] = session_data.pop("cpo_id")
                    # Legacy sessions were all served from the CPO's only menu.
                    session_data["menu_id"] = default_menu_id
                    conn.execute(S.sessions.insert().values(**session_data))
                    counts["sessions"] += 1
                    for order in order_dicts:
                        conn.execute(S.orders.insert().values(**order))
                        counts["orders"] += 1
        except Exception:
            logger.error(
                "Legacy JSON import failed while processing %s — rolling back; "
                "JSON files are untouched. Fix the file and restart.",
                current_file,
            )
            raise

    # Import committed — archive the JSON tree (best effort; the admin-row
    # guard above prevents re-import even if archiving fails).
    logger.info(
        "Legacy JSON import complete: %(cpos)d CPOs, %(menus)d menus, "
        "%(pizzas)d pizzas, %(sessions)d sessions, %(orders)d orders",
        counts,
    )
    archive_root = Path(config.DATA_DIR) / ARCHIVE_DIR_NAME
    try:
        archive_root.mkdir(parents=True, exist_ok=True)
        for cpo_dir in imported_dirs:
            os.rename(cpo_dir, archive_root / cpo_dir.name)
        # Rename in place: the config volume may be a different mount.
        os.rename(config.CONFIG_PATH, config.CONFIG_PATH + ".migrated")
        logger.info("Legacy JSON files archived under %s", archive_root)
    except OSError as exc:
        logger.warning(
            "Could not archive legacy JSON files (%s). The data was imported "
            "and will not be re-imported; you may archive the files manually.",
            exc,
        )
