from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.base import get_session
from app.models.user import User
from app.services.totp_service import verify_totp, generate_secret, provisioning_uri, totp_code
from app.services.qr_service import generate_qr_image
import io
from flask import send_file

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_session()
        user = db.query(User).filter_by(email=email).first()
        if user and user.is_active and user.check_password(password):
            # 2FA required?
            if getattr(user, "totp_enabled", False) and user.totp_secret:
                session["pending_2fa_user_id"] = user.id
                session.permanent = True
                return redirect(url_for("auth.verify_2fa"))
            user.last_login = datetime.now(timezone.utc)
            db.commit()
            session.permanent = True
            login_user(user, remember=True)
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            if user.has_role("kitchen"):
                return redirect(url_for("kitchen.display"))
            return redirect(url_for("admin.dashboard"))
        flash("Invalid email or password.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/verify-2fa", methods=["GET", "POST"])
def verify_2fa():
    uid = session.get("pending_2fa_user_id")
    if not uid:
        return redirect(url_for("auth.login"))
    db = get_session()
    user = db.get(User, uid)
    if not user:
        session.pop("pending_2fa_user_id", None)
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if user.totp_secret and verify_totp(user.totp_secret, code):
            session.pop("pending_2fa_user_id", None)
            user.last_login = datetime.now(timezone.utc)
            db.commit()
            session.permanent = True
            login_user(user, remember=True)
            flash("Signed in with 2FA.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Invalid authentication code.", "error")

    return render_template("auth/verify_2fa.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/security", methods=["GET", "POST"])
@login_required
def security():
    """Enable / disable 2FA for the logged-in admin."""
    db = get_session()
    user = db.get(User, current_user.id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.dashboard"))

    # Ensure pending setup secret in session
    if request.method == "POST":
        action = request.form.get("action")
        if action == "start":
            secret = generate_secret()
            session["totp_setup_secret"] = secret
            flash("Scan the QR with Google Authenticator / Authy, then enter the code to confirm.", "success")
        elif action == "confirm":
            secret = session.get("totp_setup_secret")
            code = request.form.get("code", "").strip()
            if not secret:
                flash("Start setup again.", "error")
            elif verify_totp(secret, code):
                user.totp_secret = secret
                user.totp_enabled = True
                db.commit()
                session.pop("totp_setup_secret", None)
                flash("Two-factor authentication is enabled.", "success")
            else:
                flash("Code did not match. Try again.", "error")
        elif action == "disable":
            code = request.form.get("code", "").strip()
            if user.totp_secret and verify_totp(user.totp_secret, code):
                user.totp_enabled = False
                user.totp_secret = None
                db.commit()
                flash("Two-factor authentication disabled.", "success")
            else:
                flash("Invalid code. 2FA not disabled.", "error")

    setup_secret = session.get("totp_setup_secret")
    uri = None
    if setup_secret:
        uri = provisioning_uri(setup_secret, user.email, "Megha Hotel")

    return render_template(
        "auth/security.html",
        user=user,
        setup_secret=setup_secret,
        setup_uri=uri,
        totp_enabled=bool(user.totp_enabled),
    )


@auth_bp.route("/security/qr.png")
@login_required
def security_qr():
    secret = session.get("totp_setup_secret")
    if not secret:
        return "No setup in progress", 404
    uri = provisioning_uri(secret, current_user.email, "Megha Hotel")
    png = generate_qr_image(uri, title="Megha Hotel", subtitle="2FA Setup", footer="Scan with Authenticator")
    return send_file(io.BytesIO(png), mimetype="image/png")
