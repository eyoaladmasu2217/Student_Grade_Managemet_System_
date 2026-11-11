import base64
import hashlib
import hmac
import secrets


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=64,
    )
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii")
    key_text = base64.urlsafe_b64encode(derived_key).decode("ascii")
    return f"scrypt$16384${salt_text}${key_text}"


def verify_password(password: str, password_hash: str) -> bool:
    algorithm, cost_text, salt_text, expected_key_text = password_hash.split("$", 3)
    if algorithm != "scrypt" or cost_text != "16384":
        return False

    salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
    expected_key = base64.urlsafe_b64decode(expected_key_text.encode("ascii"))
    actual_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=len(expected_key),
    )
    return hmac.compare_digest(actual_key, expected_key)


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
