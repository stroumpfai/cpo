from datetime import datetime, timezone

from models import (
    CPOStatsResponse,
    MenuStats,
    StatsPersonRow,
    StatsPlateRow,
    StatsSessionRow,
)
from services.cpo_service import get_cpo
from storage import get_general_stats, get_menu_stats, get_recent_sessions, update_cpo_fields
from utils import compute_session_status

_RECENT_SESSIONS_LIMIT = 5


def get_stats(cpo_id: str) -> CPOStatsResponse:
    cpo = get_cpo(cpo_id)
    since = cpo.stats_reset_at

    recent_sessions = [
        StatsSessionRow(
            session_id=r.id,
            session_date=r.session_date,
            start_time=r.start_time,
            end_time=r.end_time,
            status=compute_session_status(
                r.session_date, r.start_time, r.end_time, r.grace_period_minutes, r.closed_at,
            ),
            item_count=r.item_count,
        )
        for r in get_recent_sessions(cpo_id, limit=_RECENT_SESSIONS_LIMIT, since=since)
    ]

    menus = [
        MenuStats(
            menu_id=m["menu_id"],
            menu_name=m["menu_name"],
            use_count=m["use_count"],
            top_plates=[StatsPlateRow(pizza_name=name, count=count) for name, count in m["top_plates"]],
            top_people=[StatsPersonRow(member_name=name, count=count) for name, count in m["top_people"]],
        )
        for m in get_menu_stats(cpo_id, since=since)
    ]

    general = get_general_stats(cpo_id, since=since)

    return CPOStatsResponse(
        recent_sessions=recent_sessions,
        menus=menus,
        total_sessions=general["total_sessions"],
        distinct_members=general["distinct_members"],
        distinct_plates=general["distinct_plates"],
        stats_reset_at=since,
    )


def reset_stats(cpo_id: str) -> CPOStatsResponse:
    """Set the cutoff to now; no session/order rows are touched or deleted."""
    update_cpo_fields(cpo_id, stats_reset_at=datetime.now(tz=timezone.utc).isoformat())
    return get_stats(cpo_id)
