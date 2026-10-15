from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import current_user
from sqlalchemy.orm import joinedload
from app.models.base import get_session
from app.models.order import Order
from app.services.auth_service import role_required
from app.services.order_service import update_order_status
from app.services.settings_service import format_price
from app.extensions import csrf

kitchen_bp = Blueprint("kitchen", __name__)


@kitchen_bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


@kitchen_bp.route("/")
@role_required("super_admin", "manager", "kitchen")
def display():
    db = get_session()
    active = (
        db.query(Order)
        .options(joinedload(Order.table), joinedload(Order.items))
        .filter(Order.status.in_(["placed", "accepted", "preparing", "ready"]))
        .order_by(Order.created_at.asc())
        .all()
    )
    for o in active:
        _ = o.table
        _ = list(o.items)
        for it in o.items:
            _ = list(it.addons)
    return render_template("kitchen/display.html", orders=active, format_price=format_price)


@kitchen_bp.route("/api/orders")
@role_required("super_admin", "manager", "kitchen")
def api_orders():
    db = get_session()
    active = (
        db.query(Order)
        .options(joinedload(Order.table), joinedload(Order.items))
        .filter(Order.status.in_(["placed", "accepted", "preparing", "ready"]))
        .order_by(Order.created_at.asc())
        .all()
    )
    result = []
    for o in active:
        result.append({
            "id": o.id,
            "order_number": o.order_number,
            "table": o.table.table_number if o.table else "Takeaway",
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "prep_time": o.prep_time_estimate_minutes,
            "items": [
                {
                    "name": i.item_name,
                    "variant": i.variant_name,
                    "qty": i.quantity,
                    "instructions": i.special_instructions,
                    "addons": [a.addon_name for a in i.addons],
                }
                for i in o.items
            ],
            "special_instructions": o.special_instructions,
        })
    return jsonify(result)


@kitchen_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@csrf.exempt
@role_required("super_admin", "manager", "kitchen")
def update_status(order_id):
    db = get_session()
    order = db.get(Order, order_id)
    if not order:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or request.form
    new_status = data.get("status")
    note = data.get("note")
    prep = data.get("prep_time_minutes")
    prep_min = int(prep) if prep else None
    try:
        update_order_status(
            db, order, new_status,
            user_id=current_user.id, note=note, prep_time_minutes=prep_min,
        )
        db.commit()
        return jsonify({"ok": True, "status": order.status})
    except ValueError as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
