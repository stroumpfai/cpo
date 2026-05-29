from pathlib import Path

from fastapi import HTTPException, status


def _load_wordlist() -> tuple[frozenset[str], frozenset[str]]:
    """Load OWASP worst passwords list. Try multiple paths for dev/prod compatibility.

    Returns:
        Tuple of (exact_match_passwords, substring_check_passwords)
        - exact_match: full password matches (all words in the list)
        - substring_check: words 8+ chars to check as substrings (reject passwords containing long common words)
    """
    paths_to_try = [
        Path(__file__).parent / "wordlists" / "10k-worst-passwords.txt",
    ]
    for path in paths_to_try:
        if path.exists():
            words = frozenset(
                line.strip().lower()
                for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if line.strip()
            )
            # Separate into exact match and substring check (8+ chars to avoid false positives)
            exact_match = words
            substring_check = frozenset(w for w in words if len(w) >= 8)
            return exact_match, substring_check
    # Fallback: empty sets (validation will still check username + forbidden words)
    return frozenset(), frozenset()


_WORST_PASSWORDS_EXACT, _WORST_PASSWORDS_SUBSTRING = _load_wordlist()

_FORBIDDEN_SUBSTRINGS = frozenset({"cpo", "pizza", "chief", "officer"})


def validate_password(password: str, username: str) -> None:
    pw_lower = password.lower()

    # Check if password is in the OWASP list (exact match)
    if pw_lower in _WORST_PASSWORDS_EXACT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password is too common. Please choose a more unique password.",
        )

    # Check if password contains a common password (5+ chars to avoid false positives like "secure")
    if any(word in pw_lower for word in _WORST_PASSWORDS_SUBSTRING):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password is too common. Please choose a more unique password.",
        )

    if username.lower() in pw_lower:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must not contain your username.",
        )

    for word in _FORBIDDEN_SUBSTRINGS:
        if word in pw_lower:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must not contain words related to the application name, like pizza or cpo.",
            )
