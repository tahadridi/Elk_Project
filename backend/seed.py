import os

from app import create_app
from app.services.auth_service import create_user, get_user_by_username
from app.services.mongo import ensure_indexes, seed_default_settings

DEFAULT_USERS = [
    ("admin", "admin", "ADMIN_PASSWORD", "ChangeMe-Admin-123!"),
    ("analyst", "analyst", "ANALYST_PASSWORD", "ChangeMe-Analyst-123!"),
    ("user", "user", "USER_PASSWORD", "ChangeMe-User-123!"),
]


def main():
    app = create_app()
    with app.app_context():
        ensure_indexes()
        seed_default_settings()
        for username, role, env_name, fallback in DEFAULT_USERS:
            password = os.getenv(env_name, fallback)
            if get_user_by_username(username) is not None:
                print(f"User already exists: {username}")
                continue
            create_user(username, password, role, created_by="seed")
            print(f"Created user: {username} ({role})")
        print("Seed complete.")


if __name__ == "__main__":
    main()
