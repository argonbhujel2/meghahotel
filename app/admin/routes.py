from datetime import datetime, timezone
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    jsonify, send_file,
)
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.models.base import get_session
from app.models.order import Order, OrderItem
from app.models.reservation import Reservation, ReservationStatusHistory
from app.models.menu import MenuCategory, MenuItem
from app.models.table import RestaurantTable, TableQRToken
from app.models.settings import RestaurantSettings, TeamMember
from app.models.user import User, Role
from app.models.wifi import WifiSettings
from app.models.payment import Payment
from app.services.auth_service import role_required
from app.services.order_service import update_order_status
from app.services.qr_service import generate_qr_image, table_qr_url, wifi_qr_payload
from app.services.settings_service import format_price
from app.services.upload_service import upload_image
from app.extensions import csrf
import io
import json

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


@admin_bp.route("/")
@admin_bp.route("/dashboard")
@role_required("super_admin", "manager", "cashier")
def dashboard():
    db = get_session()
    today = datetime.now(timezone.utc).date()
    today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)

    total_orders_today = db.query(Order).filter(Order.created_at >= today_start).count()
    pending_orders = db.query(Order).filter(Order.status == "placed").count()
    preparing = db.query(Order).filter(Order.status.in_(["accepted", "preparing"])).count()
    ready = db.query(Order).filter(Order.status == "ready").count()
    sales_today = (
        db.query(func.coalesce(func.sum(Order.total_paisa), 0))
        .filter(Order.created_at >= today_start, Order.status.notin_(["cancelled", "rejected"]))
        .scalar()
    )
    pending_reservations = db.query(Reservation).filter(Reservation.status == "pending").count()
    confirmed_reservations = (
        db.query(Reservation)
        .filter(Reservation.status == "confirmed", Reservation.reservation_date >= today)
        .count()
    )
    active_tables = db.query(RestaurantTable).filter_by(is_active=True).count()
    recent_orders = (
        db.query(Order)
        .options(joinedload(Order.table))
        .order_by(Order.created_at.desc())
        .limit(8)
        .all()
    )
    for o in recent_orders:
        _ = o.table
    recent_reservations = (
        db.query(Reservation).order_by(Reservation.created_at.desc()).limit(5).all()
    )
    popular = (
        db.query(OrderItem.item_name, func.sum(OrderItem.quantity).label("qty"))
        .group_by(OrderItem.item_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        total_orders_today=total_orders_today,
        pending_orders=pending_orders,
        preparing=preparing,
        ready=ready,
        sales_today=sales_today or 0,
        pending_reservations=pending_reservations,
        confirmed_reservations=confirmed_reservations,
        active_tables=active_tables,
        recent_orders=recent_orders,
        recent_reservations=recent_reservations,
        popular=popular,
        format_price=format_price,
    )


# ── Menu ──────────────────────────────────────────────
@admin_bp.route("/menu")
@role_required("super_admin", "manager")
def menu_list():
    db = get_session()
    categories = db.query(MenuCategory).order_by(MenuCategory.display_order).all()
    items = db.query(MenuItem).options(joinedload(MenuItem.category)).order_by(MenuItem.display_order).all()
    for i in items:
        _ = i.category
    return render_template("admin/menu_list.html", categories=categories, items=items, format_price=format_price)


@admin_bp.route("/menu/category/new", methods=["GET", "POST"])
@admin_bp.route("/menu/category/<int:cat_id>/edit", methods=["GET", "POST"])
@role_required("super_admin", "manager")
def menu_category_edit(cat_id=None):
    db = get_session()
    cat = db.get(MenuCategory, cat_id) if cat_id else None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip().lower().replace(" ", "-")
        if not name or not slug:
            flash("Name and slug are required.", "error")
        else:
            if not cat:
                cat = MenuCategory(name=name, slug=slug)
                db.add(cat)
            else:
                cat.name = name
                cat.slug = slug
            cat.description = request.form.get("description") or None
            cat.is_active = bool(request.form.get("is_active"))
            cat.display_order = int(request.form.get("display_order") or 0)
            file = request.files.get("image_file")
            if file and file.filename:
                try:
                    cat.image_url = upload_image(file, "menu")
                except ValueError as ve:
                    flash(str(ve), "error")
                    return render_template("admin/menu_category_form.html", category=cat)
            else:
                existing = (request.form.get("image_url") or "").strip()
                if existing:
                    cat.image_url = existing
            db.commit()
            flash("Category saved.", "success")
            return redirect(url_for("admin.menu_list"))
    return render_template("admin/menu_category_form.html", category=cat)


@admin_bp.route("/menu/item/new", methods=["GET", "POST"])
@admin_bp.route("/menu/item/<int:item_id>/edit", methods=["GET", "POST"])
@role_required("super_admin", "manager")
def menu_item_edit(item_id=None):
    db = get_session()
    item = db.get(MenuItem, item_id) if item_id else None
    categories = db.query(MenuCategory).order_by(MenuCategory.display_order).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip().lower().replace(" ", "-")
        cat_id = int(request.form.get("category_id") or 0)
        price = float(request.form.get("price") or 0)
        if not name or not slug or not cat_id:
            flash("Name, slug and category are required.", "error")
        else:
            if not item:
                item = MenuItem(name=name, slug=slug, category_id=cat_id, price_paisa=int(price * 100))
                db.add(item)
            else:
                item.name = name
                item.slug = slug
                item.category_id = cat_id
                item.price_paisa = int(price * 100)
            item.short_description = request.form.get("short_description") or None
            item.description = request.form.get("description") or None
            disc = request.form.get("discounted_price")
            item.discounted_price_paisa = int(float(disc) * 100) if disc else None
            item.is_available = bool(request.form.get("is_available"))
            item.is_featured = bool(request.form.get("is_featured"))
            item.is_popular = bool(request.form.get("is_popular"))
            item.prep_time_minutes = int(request.form.get("prep_time_minutes") or 0) or None
            item.dietary_labels = request.form.get("dietary_labels") or None
            item.allergens = request.form.get("allergens") or None
            item.display_order = int(request.form.get("display_order") or 0)
            # Image: prefer newly uploaded file on this submit, else URL field
            file = request.files.get("image_file")
            if file and file.filename:
                try:
                    item.image_url = upload_image(file, "menu")
                except ValueError as e:
                    flash(str(e), "error")
                    return render_template("admin/menu_item_form.html", item=item, categories=categories)
            else:
                img = (request.form.get("image_url") or "").strip()
                item.image_url = img or None
            db.commit()
            flash("Dish saved.", "success")
            return redirect(url_for("admin.menu_list"))
    return render_template("admin/menu_item_form.html", item=item, categories=categories)


# ── Tables & QR ───────────────────────────────────────
@admin_bp.route("/tables")
@role_required("super_admin", "manager")
def tables_list():
    db = get_session()
    tables = db.query(RestaurantTable).order_by(RestaurantTable.table_number).all()
    return render_template("admin/tables.html", tables=tables)


@admin_bp.route("/tables/new", methods=["GET", "POST"])
@admin_bp.route("/tables/<int:table_id>/edit", methods=["GET", "POST"])
@role_required("super_admin", "manager")
def table_edit(table_id=None):
    db = get_session()
    table = db.get(RestaurantTable, table_id) if table_id else None
    if request.method == "POST":
        number = request.form.get("table_number", "").strip()
        if not number:
            flash("Table number is required.", "error")
        else:
            if not table:
                table = RestaurantTable(table_number=number)
                db.add(table)
                db.flush()
                token = TableQRToken(table_id=table.id, token=TableQRToken.generate_token(), is_active=True)
                db.add(token)
            else:
                table.table_number = number
            table.name = request.form.get("name") or f"Table {number}"
            table.capacity = int(request.form.get("capacity") or 4)
            table.seating_area = request.form.get("seating_area") or None
            table.is_active = bool(request.form.get("is_active"))
            db.commit()
            flash("Table saved.", "success")
            return redirect(url_for("admin.tables_list"))
    return render_template("admin/table_form.html", table=table)


@admin_bp.route("/tables/<int:table_id>/qr")
@role_required("super_admin", "manager")
def table_qr(table_id):
    db = get_session()
    table = db.get(RestaurantTable, table_id)
    if not table:
        flash("Table not found.", "error")
        return redirect(url_for("admin.tables_list"))
    token_obj = next((t for t in table.qr_tokens if t.is_active), None)
    if not token_obj:
        token_obj = TableQRToken(table_id=table.id, token=TableQRToken.generate_token(), is_active=True)
        db.add(token_obj)
        db.commit()
    url = table_qr_url(token_obj.token)
    return render_template("admin/table_qr.html", table=table, token=token_obj, qr_url=url)


@admin_bp.route("/tables/<int:table_id>/qr.png")
@role_required("super_admin", "manager")
def table_qr_png(table_id):
    db = get_session()
    table = db.get(RestaurantTable, table_id)
    token_obj = next((t for t in table.qr_tokens if t.is_active), None) if table else None
    if not token_obj:
        return "Not found", 404
    from app.services.qr_service import get_branding
    url = table_qr_url(token_obj.token)
    brand = get_branding()
    png = generate_qr_image(
        url,
        title=brand["name"],
        subtitle=f"Table {table.table_number}  ·  Scan to order",
        footer=brand["tagline"],
        logo_url=brand.get("logo_url"),
    )
    return send_file(io.BytesIO(png), mimetype="image/png", download_name=f"table-{table.table_number}-qr.png")


@admin_bp.route("/tables/<int:table_id>/regenerate-qr", methods=["POST"])
@role_required("super_admin", "manager")
def regenerate_table_qr(table_id):
    db = get_session()
    table = db.get(RestaurantTable, table_id)
    if not table:
        flash("Table not found.", "error")
        return redirect(url_for("admin.tables_list"))
    for t in table.qr_tokens:
        t.is_active = False
    new_token = TableQRToken(table_id=table.id, token=TableQRToken.generate_token(), is_active=True)
    db.add(new_token)
    db.commit()
    flash("QR code regenerated.", "success")
    return redirect(url_for("admin.table_qr", table_id=table_id))


@admin_bp.route("/tables/print-all-qr")
@role_required("super_admin", "manager")
def tables_print_all_qr():
    """Print-friendly page with QR codes for all active tables."""
    db = get_session()
    tables = (
        db.query(RestaurantTable)
        .filter_by(is_active=True)
        .order_by(RestaurantTable.table_number)
        .all()
    )
    items = []
    for table in tables:
        token_obj = next((t for t in table.qr_tokens if t.is_active), None)
        if not token_obj:
            token_obj = TableQRToken(
                table_id=table.id,
                token=TableQRToken.generate_token(),
                is_active=True,
            )
            db.add(token_obj)
            db.flush()
        url = table_qr_url(token_obj.token)
        items.append({"table": table, "token": token_obj, "qr_url": url})
    db.commit()
    return render_template("admin/tables_print_qr.html", items=items)


# ── Orders ────────────────────────────────────────────
@admin_bp.route("/orders")
@role_required("super_admin", "manager", "cashier", "waiter")
def orders_list():
    db = get_session()
    status = request.args.get("status", "")
    q = db.query(Order).options(joinedload(Order.table)).order_by(Order.created_at.desc())
    if status:
        q = q.filter(Order.status == status)
    orders = q.limit(100).all()
    for o in orders:
        _ = o.table
    return render_template("admin/orders.html", orders=orders, status_filter=status, format_price=format_price)


@admin_bp.route("/orders/<int:order_id>")
@role_required("super_admin", "manager", "cashier", "waiter")
def order_detail(order_id):
    db = get_session()
    order = (
        db.query(Order)
        .options(
            joinedload(Order.table),
            joinedload(Order.items),
            joinedload(Order.payments),
            joinedload(Order.status_history),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders_list"))
    _ = order.table
    for it in order.items:
        _ = list(it.addons)
    _ = list(order.payments)
    from app.services.order_service import allowed_next_statuses
    from app.models.rider import Rider
    next_statuses = allowed_next_statuses(order.status)
    riders = db.query(Rider).filter(Rider.is_active == True).order_by(Rider.full_name).all()  # noqa: E712
    try:
        _ = order.rider
    except Exception:
        pass
    return render_template(
        "admin/order_detail.html",
        order=order,
        format_price=format_price,
        next_statuses=next_statuses,
        riders=riders,
    )


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@role_required("super_admin", "manager", "cashier", "waiter", "kitchen")
def order_status_update(order_id):
    db = get_session()
    order = db.get(Order, order_id)
    if not order:
        if request.is_json or request.headers.get("X-Requested-With"):
            return jsonify({"error": "not_found"}), 404
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders_list"))
    body = request.get_json(silent=True) or {}
    new_status = request.form.get("status") or body.get("status")
    note = request.form.get("note") or body.get("note")
    prep = request.form.get("prep_time_minutes") or body.get("prep_time_minutes")
    prep_min = int(prep) if prep else None
    force = bool(request.form.get("force") or body.get("force"))
    if force and not current_user.has_role("super_admin", "manager"):
        force = False
    try:
        update_order_status(
            db, order, new_status,
            user_id=current_user.id, note=note,
            prep_time_minutes=prep_min, force=force,
        )
        db.commit()
        try:
            from app.services.email_service import notify_order_status
            settings = db.query(RestaurantSettings).first()
            notify_order_status(order, settings.name if settings else "Megha Hotel")
        except Exception:
            pass
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"ok": True, "status": order.status})
        flash(f"Order marked as {new_status}.", "success")
    except ValueError as e:
        db.rollback()
        if request.is_json:
            return jsonify({"error": str(e)}), 400
        flash(str(e), "error")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.route("/orders/<int:order_id>/payment", methods=["POST"])
@role_required("super_admin", "manager", "cashier")
def record_payment(order_id):
    db = get_session()
    order = db.get(Order, order_id)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders_list"))
    amount = float(request.form.get("amount") or 0)
    method = request.form.get("method", "cash")
    ref = request.form.get("transaction_ref") or None
    if amount <= 0:
        flash("Invalid amount.", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))
    payment = Payment(
        order_id=order.id,
        amount_paisa=int(amount * 100),
        method=method,
        status="completed",
        transaction_ref=ref,
        recorded_by_id=current_user.id,
    )
    db.add(payment)
    paid_total = sum(p.amount_paisa for p in order.payments) + payment.amount_paisa
    if paid_total >= order.total_paisa:
        order.payment_status = "paid"
    elif paid_total > 0:
        order.payment_status = "partially_paid"
    db.commit()
    flash("Payment recorded.", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


# ── Reservations ──────────────────────────────────────
@admin_bp.route("/reservations")
@role_required("super_admin", "manager")
def reservations_list():
    db = get_session()
    status = request.args.get("status", "")
    q = db.query(Reservation).order_by(Reservation.reservation_date.desc(), Reservation.reservation_time.desc())
    if status:
        q = q.filter(Reservation.status == status)
    reservations = q.limit(100).all()
    return render_template("admin/reservations.html", reservations=reservations, status_filter=status)


@admin_bp.route("/reservations/<int:res_id>/status", methods=["POST"])
@role_required("super_admin", "manager")
def reservation_status(res_id):
    db = get_session()
    res = db.get(Reservation, res_id)
    if not res:
        flash("Reservation not found.", "error")
        return redirect(url_for("admin.reservations_list"))
    new_status = request.form.get("status")
    note = request.form.get("note")
    table_id = request.form.get("table_id")
    if new_status:
        res.status = new_status
        if table_id:
            res.table_id = int(table_id)
        db.add(ReservationStatusHistory(
            reservation_id=res.id,
            status=new_status,
            changed_by_id=current_user.id,
            note=note,
        ))
        db.commit()
        try:
            from app.services.email_service import notify_reservation
            from app.services.settings_service import get_restaurant_settings
            settings = get_restaurant_settings()
            notify_reservation(res, settings.name if settings else "Megha Hotel")
        except Exception:
            pass
        flash(f"Reservation {new_status}.", "success")
    return redirect(url_for("admin.reservations_list"))


# ── Team / People behind hotel ────────────────────────
@admin_bp.route("/team")
@role_required("super_admin", "manager")
def team_list():
    db = get_session()
    members = db.query(TeamMember).order_by(TeamMember.display_order).all()
    return render_template("admin/team.html", members=members)


@admin_bp.route("/team/new", methods=["GET", "POST"])
@admin_bp.route("/team/<int:member_id>/edit", methods=["GET", "POST"])
@role_required("super_admin", "manager")
def team_edit(member_id=None):
    db = get_session()
    member = db.get(TeamMember, member_id) if member_id else None
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        role = request.form.get("role_title", "").strip()
        if not name or not role:
            flash("Name and role are required.", "error")
        else:
            if not member:
                member = TeamMember(full_name=name, role_title=role)
                db.add(member)
            else:
                member.full_name = name
                member.role_title = role
            member.bio = request.form.get("bio") or None
            file = request.files.get("photo_file")
            if file and file.filename:
                try:
                    member.photo_url = upload_image(file, "team")
                except ValueError as ve:
                    flash(str(ve), "error")
                    return render_template("admin/team_form.html", member=member)
            else:
                member.photo_url = (request.form.get("photo_url") or "").strip() or None
            member.phone = request.form.get("phone") or None
            member.email = request.form.get("email") or None
            member.is_visible = bool(request.form.get("is_visible"))
            member.display_order = int(request.form.get("display_order") or 0)
            db.commit()
            flash("Team member saved.", "success")
            return redirect(url_for("admin.team_list"))
    return render_template("admin/team_form.html", member=member)


@admin_bp.route("/team/<int:member_id>/delete", methods=["POST"])
@role_required("super_admin", "manager")
def team_delete(member_id):
    db = get_session()
    member = db.get(TeamMember, member_id)
    if member:
        db.delete(member)
        db.commit()
        flash("Team member removed.", "success")
    return redirect(url_for("admin.team_list"))



# ── Settings ──────────────────────────────────────────
@admin_bp.route("/settings", methods=["GET", "POST"])
@role_required("super_admin", "manager")
def settings():
    import json
    db = get_session()
    settings = db.query(RestaurantSettings).first()

    def _hours_dict(s):
        if s and s.opening_hours:
            try:
                return json.loads(s.opening_hours)
            except Exception:
                pass
        return {}

    if request.method == "POST":
        if not settings:
            settings = RestaurantSettings()
            db.add(settings)
        settings.name = request.form.get("name") or settings.name
        settings.tagline = request.form.get("tagline") or settings.tagline
        settings.phone = request.form.get("phone") or None
        settings.whatsapp = request.form.get("whatsapp") or None
        settings.email = request.form.get("email") or None
        settings.address = request.form.get("address") or None
        settings.map_url = request.form.get("map_url") or None
        settings.about_text = request.form.get("about_text") or None
        settings.hero_title = request.form.get("hero_title") or None
        settings.hero_subtitle = request.form.get("hero_subtitle") or None

        hero_f = request.files.get("hero_file")
        if hero_f and hero_f.filename:
            try:
                settings.hero_image_url = upload_image(hero_f, "settings")
            except ValueError as ve:
                flash(str(ve), "error")
                return render_template("admin/settings.html", settings=settings, hours=_hours_dict(settings))
        else:
            val = request.form.get("hero_image_url")
            if val is not None:
                settings.hero_image_url = val or None

        logo_f = request.files.get("logo_file")
        if logo_f and logo_f.filename:
            try:
                settings.logo_url = upload_image(logo_f, "settings")
                settings.favicon_url = settings.logo_url
                try:
                    from app.services.pwa_icons import save_pwa_icons
                    r = save_pwa_icons(settings.logo_url)
                    if r:
                        flash('Logo saved and PWA install icons updated.', 'success')
                except Exception:
                    pass
            except ValueError as ve:
                flash(str(ve), "error")
                return render_template("admin/settings.html", settings=settings, hours=_hours_dict(settings))
        else:
            val = request.form.get("logo_url")
            if val is not None:
                settings.logo_url = val or None
                if val:
                    settings.favicon_url = val
                    try:
                        from app.services.pwa_icons import save_pwa_icons
                        save_pwa_icons(val)
                    except Exception:
                        pass

        settings.primary_color = request.form.get("primary_color") or settings.primary_color
        settings.accent_color = request.form.get("accent_color") or settings.accent_color
        settings.seo_title = request.form.get("seo_title") or None
        settings.seo_description = request.form.get("seo_description") or None
        settings.takeaway_enabled = bool(request.form.get("takeaway_enabled"))
        settings.reservation_enabled = bool(request.form.get("reservation_enabled"))
        settings.tax_rate_percent = float(request.form.get("tax_rate_percent") or 0)
        settings.service_charge_percent = float(request.form.get("service_charge_percent") or 0)
        pay_f = request.files.get("payment_qr_file")
        if pay_f and pay_f.filename:
            try:
                settings.payment_qr_image_url = upload_image(pay_f, "payment")
            except ValueError as ve:
                flash(str(ve), "error")
                return render_template("admin/settings.html", settings=settings, hours=_hours_dict(settings))
        else:
            val = request.form.get("payment_qr_image_url")
            if val is not None:
                settings.payment_qr_image_url = val.strip() or None
        settings.payment_instructions = request.form.get("payment_instructions") or None
        try:
            settings.play_store_url = (request.form.get("play_store_url") or "").strip() or None
        except Exception:
            pass

        try:
            settings.delivery_enabled = bool(request.form.get("delivery_enabled"))
            settings.delivery_radius_km = float(request.form.get("delivery_radius_km") or 5)
            lat = request.form.get("delivery_center_lat")
            lng = request.form.get("delivery_center_lng")
            settings.delivery_center_lat = float(lat) if lat else None
            settings.delivery_center_lng = float(lng) if lng else None
            fee = float(request.form.get("delivery_fee_npr") or 0)
            settings.delivery_fee_paisa = int(fee * 100)
            try:
                settings.delivery_fee_per_km_paisa = int(float(request.form.get("delivery_fee_per_km_npr") or 0) * 100)
                settings.delivery_free_within_km = float(request.form.get("delivery_free_within_km") or 0)
            except Exception:
                pass
            settings.delivery_areas_text = (request.form.get("delivery_areas_text") or "").strip() or None
        except Exception:
            pass


        hours = {}
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            o = request.form.get(f"{day}_open")
            c = request.form.get(f"{day}_close")
            if o and c:
                hours[day] = {"open": o, "close": c}
        if hours:
            settings.opening_hours = json.dumps(hours)

        db.commit()
        flash("Settings saved. Contact info and hours now show on the public site.", "success")
        return redirect(url_for("admin.settings"))

    return render_template("admin/settings.html", settings=settings, hours=_hours_dict(settings))


# ── Wi-Fi ─────────────────────────────────────────────
@admin_bp.route("/wifi", methods=["GET", "POST"])
@role_required("super_admin", "manager")
def wifi_settings():
    db = get_session()
    wifi = db.query(WifiSettings).first()
    if request.method == "POST":
        if not wifi:
            wifi = WifiSettings()
            db.add(wifi)
        wifi.ssid = request.form.get("ssid", "").strip()
        wifi.password = request.form.get("password", "")
        wifi.security_type = request.form.get("security_type", "WPA")
        wifi.is_hidden = bool(request.form.get("is_hidden"))
        wifi.instructions = request.form.get("instructions") or None
        wifi.is_active = bool(request.form.get("is_active"))
        db.commit()
        flash("Wi-Fi settings saved.", "success")
        return redirect(url_for("admin.wifi_settings"))
    qr_data = wifi_qr_payload(wifi) if wifi and wifi.ssid else None
    return render_template("admin/wifi.html", wifi=wifi, qr_data=qr_data)


@admin_bp.route("/wifi/qr.png")
@role_required("super_admin", "manager")
def wifi_qr_png():
    from app.services.qr_service import get_branding
    db = get_session()
    wifi = db.query(WifiSettings).first()
    if not wifi or not wifi.ssid:
        return "Not configured", 404
    payload = wifi_qr_payload(wifi)
    brand = get_branding()
    png = generate_qr_image(
        payload,
        title=brand["name"],
        subtitle="Scan for Wi-Fi",
        footer=brand["tagline"],
        logo_url=brand.get("logo_url"),
    )
    return send_file(io.BytesIO(png), mimetype="image/png", download_name="wifi-qr.png")




# ── Staff ─────────────────────────────────────────────
@admin_bp.route("/staff")
@role_required("super_admin")
def staff_list():
    db = get_session()
    users = db.query(User).options(joinedload(User.roles)).order_by(User.full_name).all()
    for u in users:
        _ = list(u.roles)
    roles = db.query(Role).all()
    return render_template("admin/staff.html", users=users, roles=roles)


@admin_bp.route("/staff/new", methods=["GET", "POST"])
@role_required("super_admin")
def staff_new():
    db = get_session()
    roles = db.query(Role).all()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        role_ids = request.form.getlist("roles")
        if not email or not name or not password:
            flash("All fields are required.", "error")
        elif db.query(User).filter_by(email=email).first():
            flash("Email already registered.", "error")
        else:
            user = User(email=email, full_name=name, is_active=True)
            user.set_password(password)
            for rid in role_ids:
                role = db.get(Role, int(rid))
                if role:
                    user.roles.append(role)
            db.add(user)
            db.commit()
            flash("Staff account created.", "success")
            return redirect(url_for("admin.staff_list"))
    return render_template("admin/staff_form.html", roles=roles, user=None)



# ── Image upload (file picker) ────────────────────────
@admin_bp.route("/upload", methods=["POST"])
@role_required("super_admin", "manager")
def upload_file():
    f = request.files.get("file")
    subdir = request.form.get("folder") or request.args.get("folder") or "misc"
    allowed_folders = {"menu", "team", "gallery", "settings", "payment", "misc"}
    if subdir not in allowed_folders:
        subdir = "misc"
    try:
        url = upload_image(f, subdir)
        if not url:
            return jsonify({"error": "No file provided"}), 400
        return jsonify({"ok": True, "url": url})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Upload failed"}), 500


# ── Manual order (staff) ──────────────────────────────
@admin_bp.route("/orders/manual", methods=["GET", "POST"])
@role_required("super_admin", "manager", "cashier", "waiter")
def manual_order():
    from app.services.order_service import create_order
    from app.models.menu import MenuItem
    db = get_session()
    tables = db.query(RestaurantTable).filter_by(is_active=True).order_by(RestaurantTable.table_number).all()
    items = (
        db.query(MenuItem)
        .filter(MenuItem.is_available == True)  # noqa: E712
        .order_by(MenuItem.name)
        .all()
    )
    if request.method == "POST":
        email = (request.form.get("customer_email") or "").strip()
        if not email or "@" not in email:
            flash("Customer email is required.", "error")
            return render_template("admin/manual_order.html", tables=tables, items=items, format_price=format_price)
        order_type = request.form.get("order_type") or "dine_in"
        table_id = request.form.get("table_id")
        name = request.form.get("customer_name") or None
        phone = request.form.get("customer_phone") or None
        special = request.form.get("special_instructions") or None

        # Build items from form: item_id_qty
        cart = []
        for item in items:
            qty = int(request.form.get(f"qty_{item.id}") or 0)
            if qty > 0:
                cart.append({
                    "menu_item_id": item.id,
                    "variant_id": None,
                    "quantity": qty,
                    "addon_ids": [],
                    "special_instructions": None,
                })
        if not cart:
            flash("Select at least one dish.", "error")
            return render_template("admin/manual_order.html", tables=tables, items=items, format_price=format_price)

        table_token = None
        if order_type == "dine_in" and table_id:
            table = db.get(RestaurantTable, int(table_id))
            if table:
                tok = next((t for t in table.qr_tokens if t.is_active), None)
                if tok:
                    table_token = tok.token
                else:
                    tok = TableQRToken(table_id=table.id, token=TableQRToken.generate_token(), is_active=True)
                    db.add(tok)
                    db.flush()
                    table_token = tok.token

        try:
            order = create_order(
                db,
                order_type=order_type if table_token else "takeaway",
                table_token=table_token,
                items=cart,
                special_instructions=special,
                customer_name=name,
                customer_phone=phone,
                customer_email=email,
            )
            db.commit()
            try:
                from app.services.email_service import notify_order_placed
                settings = db.query(RestaurantSettings).first()
                _ = list(order.items)
                notify_order_placed(order, settings.name if settings else "Megha Hotel")
            except Exception:
                pass
            flash(f"Manual order {order.order_number} created.", "success")
            return redirect(url_for("admin.order_detail", order_id=order.id))
        except ValueError as e:
            db.rollback()
            flash(str(e), "error")

    return render_template("admin/manual_order.html", tables=tables, items=items, format_price=format_price)



# ── Riders / Delivery ─────────────────────────────────
@admin_bp.route("/riders")
@role_required("super_admin", "manager")
def riders_list():
    from app.models.rider import Rider
    db = get_session()
    riders = db.query(Rider).order_by(Rider.full_name).all()
    return render_template("admin/riders.html", riders=riders)


@admin_bp.route("/riders/new", methods=["GET", "POST"])
@admin_bp.route("/riders/<int:rider_id>/edit", methods=["GET", "POST"])
@role_required("super_admin", "manager")
def rider_edit(rider_id=None):
    from app.models.rider import Rider
    db = get_session()
    rider = db.get(Rider, rider_id) if rider_id else None
    if request.method == "POST":
        if not rider:
            rider = Rider(full_name="", phone="")
            db.add(rider)
        rider.full_name = (request.form.get("full_name") or "").strip()
        rider.phone = (request.form.get("phone") or "").strip()
        rider.vehicle_type = request.form.get("vehicle_type") or None
        rider.vehicle_number = request.form.get("vehicle_number") or None
        rider.notes = request.form.get("notes") or None
        rider.is_active = bool(request.form.get("is_active"))
        rider.is_available = bool(request.form.get("is_available"))
        username = (request.form.get("username") or "").strip().lower()
        if username:
            # unique check
            other = db.query(Rider).filter(Rider.username == username, Rider.id != (rider.id or 0)).first()
            if other:
                flash("Username already taken.", "error")
                return render_template("admin/rider_form.html", rider=rider)
            rider.username = username
        password = request.form.get("password") or ""
        if password:
            rider.set_password(password)
        if not rider.username:
            flash("Username is required for rider login.", "error")
            return render_template("admin/rider_form.html", rider=rider)
        if not rider.password_hash:
            flash("Password is required for new riders.", "error")
            return render_template("admin/rider_form.html", rider=rider)
        try:
            lat = request.form.get("last_lat")
            lng = request.form.get("last_lng")
            rider.last_lat = float(lat) if lat else rider.last_lat
            rider.last_lng = float(lng) if lng else rider.last_lng
        except ValueError:
            pass
        file = request.files.get("photo_file")
        if file and file.filename:
            try:
                rider.photo_url = upload_image(file, "misc")
            except ValueError as e:
                flash(str(e), "error")
                return render_template("admin/rider_form.html", rider=rider)
        if not rider.full_name or not rider.phone:
            flash("Name and phone required.", "error")
            return render_template("admin/rider_form.html", rider=rider)
        db.commit()
        flash("Rider saved.", "success")
        return redirect(url_for("admin.riders_list"))
    return render_template("admin/rider_form.html", rider=rider)


@admin_bp.route("/orders/<int:order_id>/assign-rider", methods=["POST"])
@role_required("super_admin", "manager", "cashier")
def assign_rider(order_id):
    from app.models.rider import Rider
    from app.models.order import Order
    db = get_session()
    order = db.get(Order, order_id)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders_list"))
    rider_id = request.form.get("rider_id")
    status = request.form.get("delivery_status") or order.delivery_status or "pending_pickup"
    if rider_id:
        order.rider_id = int(rider_id)
    order.delivery_status = status
    db.commit()
    # Email customer when rider assigned
    try:
        if rider_id:
            from app.models.rider import Rider as RiderModel
            from app.services.email_service import notify_rider_assigned
            from app.services.settings_service import get_restaurant_settings
            rider = db.get(RiderModel, int(rider_id))
            settings = get_restaurant_settings()
            if rider:
                notify_rider_assigned(order, rider, settings.name if settings else "Megha Hotel")
    except Exception:
        pass
    flash("Delivery / rider updated.", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))



@admin_bp.route("/riders/<int:rider_id>/location", methods=["POST"])
@role_required("super_admin", "manager", "cashier", "waiter")
def rider_location(rider_id):
    """Update rider GPS position for live map tracking."""
    from app.models.rider import Rider
    from datetime import datetime, timezone
    db = get_session()
    rider = db.get(Rider, rider_id)
    if not rider:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(silent=True) or {}
    try:
        lat = float(request.form.get("lat") or body.get("lat"))
        lng = float(request.form.get("lng") or body.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "lat/lng required"}), 400
    rider.last_lat = lat
    rider.last_lng = lng
    rider.last_location_at = datetime.now(timezone.utc)
    db.commit()
    if request.is_json or request.headers.get("X-Requested-With"):
        return jsonify({"ok": True, "lat": lat, "lng": lng})
    flash("Rider location updated.", "success")
    return redirect(url_for("admin.rider_edit", rider_id=rider_id))
