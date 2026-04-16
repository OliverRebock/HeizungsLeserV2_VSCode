import re

from app.core.config import settings


SPECIAL_CHARACTER_PATTERN = re.compile(r'[^A-Za-z0-9]')


def validate_password_strength(password: str) -> str:
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long")
    if password != password.strip():
        raise ValueError("Password must not start or end with whitespace")
    if any(char.isspace() for char in password):
        raise ValueError("Password must not contain whitespace")
    if password.lower() == password:
        raise ValueError("Password must contain at least one uppercase letter")
    if password.upper() == password:
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(char.isdigit() for char in password):
        raise ValueError("Password must contain at least one digit")
    if not SPECIAL_CHARACTER_PATTERN.search(password):
        raise ValueError("Password must contain at least one special character")
    return password