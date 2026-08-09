"""Stable, translatable codes for the errors the UI shows a user.

Every user-facing failure is raised as an `AppError`, which adds a snake_case
`code` and the values interpolated into the English sentence to the response
body:

    {"detail": "Name must be 100 characters or fewer.",
     "code": "name_too_long", "params": {"max": 100}}

`detail` stays English and byte-identical to what it was before codes existed —
it is the API's documented wording and the client's fallback for a code it does
not know. The React side translates `errors.<code>` with `params` instead (see
frontend/src/i18n/apiError.js).

A code is registered exactly once, per distinct failure rather than per raise
site: several call sites share a message and therefore share its code. Every
code here needs an `errors.<code>` entry in frontend/src/i18n/locales/en.json —
tests/test_error_codes.py fails if the two drift apart.
"""
from typing import Any

from fastapi import HTTPException

CODES = frozenset({
    # Auth & passwords
    "invalid_credentials",
    "too_many_logins",
    "current_password_incorrect",
    "password_too_common",
    "password_contains_username",
    "password_contains_app_name",
    # Accounts (admin panel & team management)
    "username_exists",
    "email_exists",
    "admin_not_found",
    "cpo_not_found",
    "team_not_found",
    "team_member_not_found",
    "cannot_delete_self",
    "last_admin",
    "last_team_member",
    "use_change_password",
    # Invites
    "invite_not_found",
    "invite_invalid",
    "invite_used",
    # Sessions
    "session_not_found",
    "session_closed",
    "session_already_closed",
    "session_already_open",
    "session_end_passed",
    "end_before_start",
    "no_menus",
    # Menus & items
    "menu_not_found",
    "menu_name_required",
    "menu_name_exists",
    "menu_in_use",
    "menu_import_duplicate_name",
    "pizza_not_found",
    "pizza_name_exists",
    # Public ordering page
    "team_link_not_found",
    "rate_limited",
    "name_required",
    "name_too_long",
    "email_required",
    "email_too_long",
    "invalid_email",
    "pizza_not_in_menu",
    "order_not_found",
})


class AppError(HTTPException):
    """HTTPException that also carries a stable, translatable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ):
        if code not in CODES:
            raise ValueError(f"Unregistered error code: {code!r} — add it to CODES.")
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.params = params or {}
