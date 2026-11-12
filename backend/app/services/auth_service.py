from bson import ObjectId
from bson.errors import InvalidId

import bcrypt

from ..extensions import get_db
from .mongo import utcnow
from .policy_service import VALID_ROLES


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_user_by_username(username: str):
    if not username:
        return None
    return get_db().users.find_one({"username": username.strip().lower()})


def get_user_by_id(user_id: str):
    try:
        return get_db().users.find_one({"_id": ObjectId(user_id)})
    except (InvalidId, TypeError):
        return None


def create_user(username, password, role, created_by=None):
    normalized = (username or "").strip().lower()
    if len(normalized) < 3:
        raise ValueError("Username must be at least 3 characters")
    if role not in VALID_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters")
    if get_user_by_username(normalized) is not None:
        raise ValueError("Username already exists")

    document = {
        "username": normalized,
        "password_hash": hash_password(password),
        "role": role,
        "active": True,
        "created_at": utcnow(),
        "created_by": created_by,
        "last_login_at": None,
    }
    result = get_db().users.insert_one(document)
    document["_id"] = result.inserted_id
    return document


def authenticate(username, password):
    user = get_user_by_username(username)
    if user is None or not user.get("active", True):
        return None
    if not verify_password(password or "", user.get("password_hash", "")):
        return None
    return user


def update_last_login(user_id):
    get_db().users.update_one(
        {"_id": user_id},
        {"$set": {"last_login_at": utcnow()}},
    )


def public_user(user):
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "role": user["role"],
        "active": user.get("active", True),
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
    }


def list_users():
    return [
        public_user(user)
        for user in get_db().users.find({}).sort("username", 1)
    ]


def update_user(user_id, values, updated_by):
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("User not found")

    changes = {}
    if "role" in values:
        role = values["role"]
        if role not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
        changes["role"] = role
    if "active" in values:
        changes["active"] = bool(values["active"])
    if "password" in values:
        password = values["password"]
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters")
        changes["password_hash"] = hash_password(password)

    if not changes:
        return user

    changes["updated_by"] = updated_by
    changes["updated_at"] = utcnow()
    get_db().users.update_one({"_id": user["_id"]}, {"$set": changes})
    return get_user_by_id(user_id)
