"""Rider portal – separate from admin. Login, assigned orders, pickup/deliver, GPS."""
from datetime import datetime, timezone
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, jsonify,
)
from sqlalchemy.orm import joinedload

from app.models.base import get_session
from app.models.rider import Rider
from app.models.order import Order
from app.extensions import csrf

rider_bp = Blueprint("rider", __name__, url_prefix="/rider")


def rider_login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("rider_id"):
            return redirect(url_for("rider.login", next=request.path))
        return f(*args, **kwargs)
    return wrapped


def current_rider(db):
    rid = session.get("rider_id")
    if not rid:
        return None
    return db.get(Rider, rid)


@rider_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("rider_id"):
        return redirect(url_for("rider.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        db = get_session()
        rider = db.query(Rider).filter(Rider.username == username).first()
        if rider and rider.is_active and rider.check_password(password):
            session.permanent = True
            session["rider_id"] = rider.id
            session["rider_name"] = rider.full_name
            flash(f"Welcome, {rider.full_name}.", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/rider"):
                return redirect(next_url)
            return redirect(url_for("rider.dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("rider/login.html")


@rider_bp.route("/logout")
def logout():
    session.pop("rider_id", None)
    session.pop("rider_name", None)
    flash("Signed out.", "success")
    return redirect(url_for("rider.login"))


@rider_bp.route("/")
@rider_bp.route("/dashboard")
@rider_login_required
def dashboard():
    db = get_session()
    rider = current_rider(db)
    if not rider:
        session.clear()
        return redirect(url_for("rider.login"))

    active = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(
            Order.rider_id == rider.id,
            Order.order_type == "delivery",
            Order.status.notin_(["cancelled", "rejected"]),
            Order.delivery_status.notin_(["delivered"]) if True else True,
        )
        .order_by(Order.created_at.desc())
        .all()
    )
    # Filter in python for delivery_status null or not delivered
    active = [
        o for o in active
        if (o.delivery_status or "pending_pickup") != "delivered"
        and o.status not in ("completed",)
    ]
    history = (
        db.query(Order)
        .filter(Order.rider_id == rider.id, Order.delivery_status == "delivered")
        .order_by(Order.created_at.desc())
        .limit(20)
        .all()
    )
    for o in active:
        _ = list(o.items)
    return render_template(
        "rider/dashboard.html",
        rider=rider,
        orders=active,
        history=history,
    )


@rider_bp.route("/orders/<int:order_id>")
@rider_login_required
def order_detail(order_id):
    db = get_session()
    rider = current_rider(db)
    order = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(Order.id == order_id, Order.rider_id == rider.id)
        .first()
    )
    if not order:
        flash("Order not found or not assigned to you.", "error")
        return redirect(url_for("rider.dashboard"))
    _ = list(order.items)
    return render_template("rider/order_detail.html", rider=rider, order=order)


@rider_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@rider_login_required
def order_status(order_id):
    db = get_session()
    rider = current_rider(db)
    order = db.query(Order).filter(Order.id == order_id, Order.rider_id == rider.id).first()
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("rider.dashboard"))

    new_ds = (request.form.get("delivery_status") or "").strip()
    allowed = ["pending_pickup", "picked_up", "on_the_way", "nearby", "delivered"]
    if new_ds not in allowed:
        flash("Invalid status.", "error")
        return redirect(url_for("rider.order_detail", order_id=order_id))

    order.delivery_status = new_ds
    # Mirror kitchen-ish statuses when useful
    if new_ds == "picked_up" and order.status in ("ready", "served", "accepted", "preparing"):
        pass
    if new_ds == "delivered":
        order.status = "completed"
        order.completed_at = datetime.now(timezone.utc)
        rider.is_available = True
    elif new_ds in ("picked_up", "on_the_way", "nearby"):
        rider.is_available = False

    db.commit()
    flash(f"Status updated: {new_ds}", "success")
    return redirect(url_for("rider.order_detail", order_id=order_id))


@rider_bp.route("/location", methods=["POST"])
@csrf.exempt
@rider_login_required
def update_location():
    db = get_session()
    rider = current_rider(db)
    if not rider:
        return jsonify({"error": "not logged in"}), 401
    data = request.get_json(silent=True) or request.form
    try:
        lat = float(data.get("lat"))
        lng = float(data.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "lat/lng required"}), 400
    rider.last_lat = lat
    rider.last_lng = lng
    rider.last_location_at = datetime.now(timezone.utc)
    db.commit()
    return jsonify({"ok": True, "lat": lat, "lng": lng})


@rider_bp.route("/availability", methods=["POST"])
@rider_login_required
def toggle_availability():
    db = get_session()
    rider = current_rider(db)
    rider.is_available = not rider.is_available
    db.commit()
    flash("Availability: " + ("Available" if rider.is_available else "Busy"), "success")
    return redirect(url_for("rider.dashboard"))
