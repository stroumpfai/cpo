import pytest

from password_policy import validate_password


def test_validate_password_common_password_fails():
    with pytest.raises(Exception) as exc_info:
        validate_password("password", "alice")
    assert "too common" in str(exc_info.value).lower()


def test_validate_password_username_substring_fails():
    with pytest.raises(Exception) as exc_info:
        validate_password("myalicepass", "alice")
    assert "must not contain your username" in str(exc_info.value).lower()


def test_validate_password_username_case_insensitive():
    with pytest.raises(Exception) as exc_info:
        validate_password("MyAlicePass", "alice")
    assert "must not contain your username" in str(exc_info.value).lower()


def test_validate_password_forbidden_word_cpo():
    with pytest.raises(Exception) as exc_info:
        validate_password("mycpoapp", "alice")
    assert "application name" in str(exc_info.value).lower()


def test_validate_password_forbidden_word_pizza():
    with pytest.raises(Exception) as exc_info:
        validate_password("mypizzatime", "alice")
    assert "application name" in str(exc_info.value).lower()


def test_validate_password_forbidden_word_chief():
    with pytest.raises(Exception) as exc_info:
        validate_password("chiefstuff", "alice")
    assert "application name" in str(exc_info.value).lower()


def test_validate_password_forbidden_word_officer():
    with pytest.raises(Exception) as exc_info:
        validate_password("officerdown", "alice")
    assert "application name" in str(exc_info.value).lower()


def test_validate_password_forbidden_words_case_insensitive():
    # All should raise for containing app-related words (case-insensitive)
    for pwd in ["MyCPOapp", "MyPizzaTime", "ChiefStuff", "OfficerDown"]:
        with pytest.raises(Exception) as exc_info:
            validate_password(pwd, "alice")
        assert "application name" in str(exc_info.value).lower()


def test_validate_password_valid_strong_password():
    # Should not raise
    validate_password("X9$mNqLp2!", "alice")


def test_validate_password_valid_long_random():
    # Should not raise - contains no 8+ char OWASP words
    validate_password("MyStr0ng!Pass#2024", "alice")
