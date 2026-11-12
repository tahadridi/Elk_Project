from functools import wraps

from flask_jwt_extended import get_jwt, verify_jwt_in_request

from .responses import error_response


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") not in roles:
                return error_response("FORBIDDEN", "Insufficient role", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
