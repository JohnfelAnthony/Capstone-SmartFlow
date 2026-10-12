"""
SMARTFLOW - Authentication & Session Management
"""

import config

LANDING_ROUTE_ORDER = (
    ("dashboard", "view", "/dashboard"),
    ("simulation", "view", "/simulation"),
    ("scenarios", "view", "/scenarios"),
    ("performance", "view", "/performance"),
    ("ai-agent", "view", "/ai-agent"),
    ("rl-training", "view", "/rl-training"),
    ("runs-reports", "view", "/runs-reports"),
    ("profile", "view", "/profile"),
    ("help", "view", "/help"),
)

def hash_password(password: str) -> str:
    from werkzeug.security import generate_password_hash

    return generate_password_hash(password)


def verify_password(password: str, hashed: str) -> bool:
    from werkzeug.security import check_password_hash

    return check_password_hash(hashed, password)


def validate_password_strength(password: str) -> list[str]:
    errors = []
    if len(password) < config.MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters")
    if not any(character.isupper() for character in password):
        errors.append("Password must contain at least one uppercase letter")
    if not any(character.islower() for character in password):
        errors.append("Password must contain at least one lowercase letter")
    if not any(character.isdigit() for character in password):
        errors.append("Password must contain at least one digit")
    return errors
