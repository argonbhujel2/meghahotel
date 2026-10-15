"""Customer order submission, cancel, and staff manual orders."""
import uuid
from flask import Blueprint, request, jsonify, session as flask_session
from app.models.base import get_session
from app.services.order_service import create_order, update_order_status, get_order_by_tracking
from app.extensions import csrf

orders_bp = Blueprint("orders", __name__)


@orders_bp.route("/submit", methods=["POST"])
@csrf.exempt
def submit_order():
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    special = data.get("special_instructions")
    customer_name = (data.get("customer_name") or "").strip() or None
    customer_phone = (data.get("customer_phone") or "").strip() or None
    customer_email = (data.get("customer_email") or "").strip() or None
    order_type = data.get("order_type") or "dine_in"
    delivery_address = (data.get("delivery_address") or "").strip() or None
    delivery_notes = (data.get("delivery_notes") or "").strip() or None
    try:
        delivery_fee_paisa = int(data.get("delivery_fee_paisa") or 0)
    except (TypeError, ValueError):
        delivery_fee_paisa = 0
    try:
        customer_lat = float(data["customer_lat"]) if data.get("customer_lat") not in (None, "") else None
        customer_lng = float(data["customer_lng"]) if data.get("customer_lng") not in (None, "") else None
    except (TypeError, ValueError):
        customer_lat = customer_lng = None
    table_token = data.get("table_token") or flask_session.get("table_token")
    idempotency_key = (
        data.get("idempotency_key")
        or request.headers.get("X-Idempotency-Key")
        or str(uuid.uuid4())
    )

    if order_type == "delivery":
        pass
    elif not table_token:
        order_type = "takeaway"

    if not customer_email or "@" not in customer_email:
        return jsonify({"error": "Email is required."}), 400

    if not items:
        return jsonify({"error": "Cart is empty. Add items from the menu first."}), 400

    normalized = []
    for raw in items:
        mid = raw.get("menu_item_id")
        if not mid:
            continue
        normalized.append({
            "menu_item_id": int(mid),
            "variant_id": int(raw["variant_id"]) if raw.get("variant_id") else None,
            "quantity": max(1, int(raw.get("quantity") or 1)),
            "addon_ids": [int(a) for a in (raw.get("addon_ids") or [])],
            "special_instructions": raw.get("special_instructions"),
        })
    if not normalized:
        return jsonify({"error": "No valid items in cart."}), 400

    db = get_session()
    try:
        order = create_order(
            db,
            order_type=order_type,
            table_token=table_token if order_type == "dine_in" else None,
            items=normalized,
            special_instructions=special,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            delivery_address=delivery_address,
            delivery_notes=delivery_notes,
            delivery_fee_paisa=delivery_fee_paisa,
            customer_lat=customer_lat,
            customer_lng=customer_lng,
            idempotency_key=idempotency_key,
        )
        db.commit()
        try:
            from app.services.email_service import notify_order_placed
            from app.models.settings import RestaurantSettings
            settings = db.query(RestaurantSettings).first()
            name = settings.name if settings else "Megha Hotel"
            # reload items for email
            _ = list(order.items)
            notify_order_placed(order, name)
        except Exception:
            pass
        return jsonify({
            "ok": True,
            "order_number": order.order_number,
            "tracking_token": order.tracking_token,
            "tracking_url": f"/track/{order.tracking_token}",
            "total_paisa": order.total_paisa,
        }), 201
    except ValueError as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception:
        db.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Unable to place order. Please try again."}), 500


@orders_bp.route("/cancel/<token>", methods=["POST"])
@csrf.exempt
def cancel_order(token):
    """Customer can cancel only while status is 'placed'."""
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "Cancelled by customer").strip()
    db = get_session()
    order = get_order_by_tracking(db, token)
    if not order:
        return jsonify({"error": "Order not found."}), 404
    if order.status != "placed":
        return jsonify({"error": "This order can no longer be cancelled. Please contact the restaurant."}), 400
    try:
        update_order_status(db, order, "cancelled", note=reason)
        db.commit()
        try:
            from app.services.email_service import notify_order_status
            from app.models.settings import RestaurantSettings
            settings = db.query(RestaurantSettings).first()
            notify_order_status(order, settings.name if settings else "Megha Hotel")
        except Exception:
            pass
        return jsonify({"ok": True, "status": "cancelled"})
    except ValueError as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
