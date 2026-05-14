from collections import defaultdict

from models import DistributionRow, PizzeriaRow, SessionFile, SummaryResponse
from utils import compute_session_status


def build_summary(session: SessionFile) -> SummaryResponse:
    status = compute_session_status(
        session.session_date,
        session.start_time,
        session.end_time,
        session.grace_period_minutes,
    )

    distribution = sorted(
        [
            DistributionRow(
                order_id=o.id,
                member_name=o.member_name,
                client_ip=o.client_ip,
                pizza_name=o.pizza_name,
                price=o.pizza_price,
            )
            for o in session.orders
        ],
        key=lambda r: r.member_name.lower(),
    )

    agg: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0.0})
    for o in session.orders:
        agg[o.pizza_name]["count"] += 1
        agg[o.pizza_name]["total"] += o.pizza_price

    pizzeria = [
        PizzeriaRow(pizza_name=name, count=d["count"], total_price=round(d["total"], 2))
        for name, d in sorted(agg.items())
    ]

    return SummaryResponse(
        session_id=session.id,
        status=status,
        distribution=distribution,
        pizzeria=pizzeria,
        total_orders=len(session.orders),
        total_price=round(sum(o.pizza_price for o in session.orders), 2),
    )
