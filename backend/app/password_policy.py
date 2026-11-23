import re

COMMON_PASSWORDS = frozenset(
    {
        "password123456",
        "password12345",
        "qwerty123456",
        "letmein12345",
        "adminadmin123",
        "welcome123456",
        "123456789012",
        "aaaaaaaaaaaa",
    }
)
SIMPLE_SEQUENCES = re.compile(r"(0123|1234|2345|3456|4567|5678|6789|abcd|qwer)")


def validate_password(password: str, email: str | None = None) -> str:
    lowered = password.casefold()
    if lowered in COMMON_PASSWORDS:
        raise ValueError("Choose a password that is not commonly used")
    if len(set(password)) < 4:
        raise ValueError("Password must contain at least four distinct characters")
    if SIMPLE_SEQUENCES.search(lowered):
        raise ValueError("Password must not contain a simple sequence")
    if email:
        local_part = email.split("@", 1)[0].casefold()
        if len(local_part) >= 4 and local_part in lowered:
            raise ValueError("Password must not contain your email name")
    return password
