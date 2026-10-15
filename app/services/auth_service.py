from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_role(*roles) and not current_user.has_role("super_admin"):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def permission_required(permission: str):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_permission(permission):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator
