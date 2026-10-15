from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, request, Response, redirect, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.models.base import get_session
from app.models.order import Order, OrderItem
from app.models.reservation import Reservation
from app.services.auth_service import role_required
from app.services.settings_service import format_price
import csv
import io

reports_bp = Blueprint("reports", __name__)


@reports_bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


@reports_bp.route("/")
@role_required("super_admin", "manager")
def index():
    db = get_session()
    days = int(request.args.get("days") or 7)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    sales = (
        db.query(func.coalesce(func.sum(Order.total_paisa), 0))
        .filter(Order.created_at >= since, Order.status.notin_(["cancelled", "rejected"]))
        .scalar()
    )
    order_count = (
        db.query(Order)
        .filter(Order.created_at >= since, Order.status.notin_(["cancelled", "rejected"]))
        .count()
    )
    cancelled = (
        db.query(Order)
        .filter(Order.created_at >= since, Order.status.in_(["cancelled", "rejected"]))
        .count()
    )
    top_items = (
        db.query(
            OrderItem.item_name,
            func.sum(OrderItem.quantity).label("qty"),
            func.sum(OrderItem.line_total_paisa).label("revenue"),
        )
        .join(Order)
        .filter(Order.created_at >= since, Order.status.notin_(["cancelled", "rejected"]))
        .group_by(OrderItem.item_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(10)
        .all()
    )
    res_count = db.query(Reservation).filter(Reservation.created_at >= since).count()
    res_confirmed = (
        db.query(Reservation)
        .filter(Reservation.created_at >= since, Reservation.status == "confirmed")
        .count()
    )

    return render_template(
        "admin/reports.html",
        days=days,
        sales=sales or 0,
        order_count=order_count,
        cancelled=cancelled,
        top_items=top_items,
        res_count=res_count,
        res_confirmed=res_confirmed,
        format_price=format_price,
    )


@reports_bp.route("/export/orders.csv")
@role_required("super_admin", "manager")
def export_orders_csv():
    db = get_session()
    days = int(request.args.get("days") or 30)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    orders = (
        db.query(Order)
        .options(joinedload(Order.table))
        .filter(Order.created_at >= since)
        .order_by(Order.created_at.desc())
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Order Number", "Date", "Type", "Table", "Status", "Payment", "Total (NPR)"])
    for o in orders:
        writer.writerow([
            o.order_number,
            o.created_at.isoformat() if o.created_at else "",
            o.order_type,
            o.table.table_number if o.table else "",
            o.status,
            o.payment_status,
            f"{o.total_paisa / 100:.2f}",
        ])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )
