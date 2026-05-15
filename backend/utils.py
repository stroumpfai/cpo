import secrets
import string
import uuid
from datetime import date, datetime, timedelta, timezone

import bcrypt

from config import BCRYPT_ROUNDS, GRACE_PERIOD_MINUTES, MIN_LINK_LENGTH


def new_id() -> str:
    return str(uuid.uuid4())


def generate_link(length: int = MIN_LINK_LENGTH) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def now_utc() -> datetime:
    # Session times are stored in UTC; always compare against UTC.
    # replace(tzinfo=None) strips awareness so it compares with naive session_datetime() results.
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def session_datetime(session_date: date, hhmm: str) -> datetime:
    """Combine a date and an 'HH:MM' string into a naive UTC datetime."""
    h, m = map(int, hhmm.split(":"))
    return datetime(session_date.year, session_date.month, session_date.day, h, m)


def compute_session_status(
    session_date: date,
    start_time: str,
    end_time: str,
    grace_period_minutes: int = GRACE_PERIOD_MINUTES,
    closed_at=None,
) -> str:
    if closed_at is not None:
        return "closed"

    now = now_utc()
    start_dt = session_datetime(session_date, start_time)
    end_dt = session_datetime(session_date, end_time)
    close_dt = end_dt + timedelta(minutes=grace_period_minutes)

    if now < start_dt:
        return "upcoming"
    if now <= close_dt:
        return "active"
    return "closed"
