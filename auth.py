import functools
from flask import session, redirect, url_for, flash, request


def current_user_id():
    return session.get("user_id")


def current_role():
    return session.get("role")


def login_required(role=None):
    """
    Decorator that requires a logged-in user.
    If `role` is given ("hr" or "candidate"), the logged-in user must have that role.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login_hr" if role == "hr" else "login_candidate" if role == "candidate" else "landing"))
            if role and session.get("role") != role:
                flash("You don't have access to that page.", "error")
                if session.get("role") == "hr":
                    return redirect(url_for("index"))
                elif session.get("role") == "candidate":
                    return redirect(url_for("candidate_dashboard"))
                return redirect(url_for("landing"))
            return f(*args, **kwargs)
        return wrapped
    return decorator
