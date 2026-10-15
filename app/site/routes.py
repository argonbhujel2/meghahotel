from flask import (
    abort,
    Blueprint, render_template, request, redirect, url_for, flash,
    session as flask_session, jsonify,
)
from app.models.base import get_session
from app.models.settings import (
    RestaurantSettings, Testimonial, GalleryImage, Announcement, SocialLink, TeamMember,
)
from app.models.menu import MenuCategory, MenuItem
from app.models.table import TableQRToken

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    from sqlalchemy.orm import joinedload
    from flask import current_app
    try:
        db = get_session()
        settings = db.query(RestaurantSettings).first()
    except Exception as e:
        # Tables may not exist yet – try one-time init
        current_app.logger.warning(f"DB not ready, running init_db: {e}")
        try:
            from app.models.base import init_db
            init_db(current_app)
            db = get_session()
            settings = db.query(RestaurantSettings).first()
        except Exception as e2:
            current_app.logger.error(f"init_db failed: {e2}")
            return render_template(
                "errors/500.html",
                error_hint="Database tables are missing. Check TURSO credentials and redeploy.",
            ), 500
    featured = (
        db.query(MenuItem)
        .options(joinedload(MenuItem.category))
        .filter(MenuItem.is_featured == True, MenuItem.is_available == True)  # noqa: E712
        .order_by(MenuItem.display_order)
        .limit(6)
        .all()
    )
    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.is_active == True)  # noqa: E712
        .order_by(MenuCategory.display_order)
        .all()
    )
    testimonials = (
        db.query(Testimonial)
        .filter(Testimonial.is_visible == True)  # noqa: E712
        .order_by(Testimonial.display_order)
        .limit(6)
        .all()
    )
    gallery = (
        db.query(GalleryImage)
        .filter(GalleryImage.is_visible == True)  # noqa: E712
        .order_by(GalleryImage.display_order)
        .limit(8)
        .all()
    )
    announcement = (
        db.query(Announcement)
        .filter(Announcement.is_active == True)  # noqa: E712
        .order_by(Announcement.id.desc())
        .first()
    )
    socials = (
        db.query(SocialLink)
        .filter(SocialLink.is_visible == True)  # noqa: E712
        .order_by(SocialLink.display_order)
        .all()
    )
    team = (
        db.query(TeamMember)
        .filter(TeamMember.is_visible == True)  # noqa: E712
        .order_by(TeamMember.display_order)
        .all()
    )
    import json
    hours = {}
    if settings and settings.opening_hours:
        try:
            hours = json.loads(settings.opening_hours)
        except Exception:
            hours = {}
    return render_template(
        "public/index.html",
        settings=settings,
        featured=featured,
        categories=categories,
        testimonials=testimonials,
        gallery=gallery,
        announcement=announcement,
        socials=socials,
        team=team,
        hours=hours,
    )


@public_bp.route("/menu")
def menu():
    db = get_session()
    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.is_active == True)  # noqa: E712
        .order_by(MenuCategory.display_order)
        .all()
    )
    q = request.args.get("q", "").strip()
    cat_slug = request.args.get("category", "")
    from sqlalchemy.orm import joinedload
    items_q = db.query(MenuItem).filter(MenuItem.is_available == True)  # noqa: E712
    if q:
        items_q = items_q.filter(MenuItem.name.ilike(f"%{q}%"))
    if cat_slug:
        cat = db.query(MenuCategory).filter_by(slug=cat_slug).first()
        if cat:
            items_q = items_q.filter(MenuItem.category_id == cat.id)
    items = items_q.options(joinedload(MenuItem.category)).order_by(MenuItem.display_order).all()
    table_token = flask_session.get("table_token")
    return render_template(
        "public/menu.html",
        categories=categories,
        items=items,
        search_q=q,
        active_category=cat_slug,
        table_token=table_token,
    )


@public_bp.route("/menu/<slug>")
def menu_item_detail(slug):
    db = get_session()
    item = db.query(MenuItem).filter_by(slug=slug).first()
    if not item:
        abort(404)
    return render_template("public/menu_item.html", item=item)


@public_bp.route("/t/<token>")
def table_order(token):
    """QR entry point – bind table token to session and open menu."""
    db = get_session()
    qr = (
        db.query(TableQRToken)
        .filter_by(token=token, is_active=True)
        .first()
    )
    if not qr or not qr.table or not qr.table.is_active:
        flash("This table QR code is invalid or inactive.", "error")
        return redirect(url_for("public.menu"))
    flask_session["table_token"] = token
    flask_session["table_number"] = qr.table.table_number
    flask_session["table_id"] = qr.table.id
    flash(f"Welcome! You are ordering for Table {qr.table.table_number}.", "success")
    return redirect(url_for("public.menu"))


@public_bp.route("/cart")
def cart():
    table_token = flask_session.get("table_token")
    table_number = flask_session.get("table_number")
    return render_template(
        "public/cart.html",
        table_token=table_token,
        table_number=table_number,
    )


@public_bp.route("/track", methods=["GET", "POST"])
def track_lookup():
    from app.models.order import Order
    from sqlalchemy.orm import joinedload
    if request.method == "POST":
        order_number = (request.form.get("order_number") or "").strip().upper()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        if not order_number:
            flash("Please enter your order number.", "error")
            return render_template("public/track_lookup.html")
        if not email and not phone:
            flash("Enter the email or phone used when ordering.", "error")
            return render_template("public/track_lookup.html")
        db = get_session()
        order = (
            db.query(Order)
            .options(joinedload(Order.table), joinedload(Order.items))
            .filter(Order.order_number == order_number)
            .first()
        )
        if not order:
            flash("Order not found. Check the order number.", "error")
            return render_template("public/track_lookup.html")
        # Verify email or phone matches
        match = False
        if email and order.customer_email and order.customer_email.strip().lower() == email:
            match = True
        if phone and order.customer_phone:
            # normalize digits
            def digits(s):
                return "".join(c for c in (s or "") if c.isdigit())
            if digits(phone) and digits(phone) == digits(order.customer_phone):
                match = True
        if not match:
            flash("Email or phone does not match this order.", "error")
            return render_template("public/track_lookup.html")
        for it in order.items:
            _ = list(it.addons)
        return redirect(url_for("public.track_order", token=order.tracking_token))
    return render_template("public/track_lookup.html")


@public_bp.route("/track/<token>")
def track_order(token):
    from app.services.order_service import get_order_by_tracking
    db = get_session()
    order = get_order_by_tracking(db, token)
    if not order:
        flash("Order not found. Please check your tracking link.", "error")
        return redirect(url_for("public.track_lookup"))
    # Force-load relationships while session is open
    _ = order.table
    items = list(order.items)
    for it in items:
        _ = list(it.addons)
    return render_template("public/track.html", order=order)


@public_bp.route("/api/track/<token>")
def api_track_order(token):
    """JSON endpoint for polling order status."""
    from app.services.order_service import get_order_by_tracking
    db = get_session()
    order = get_order_by_tracking(db, token)
    if not order:
        return jsonify({"error": "not_found"}), 404
    table_number = order.table.table_number if order.table else None
    return jsonify({
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "total_paisa": order.total_paisa,
        "prep_time_estimate_minutes": order.prep_time_estimate_minutes,
        "table_number": table_number,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    })


@public_bp.route("/contact")
def contact():
    import json
    db = get_session()
    settings = db.query(RestaurantSettings).first()
    socials = db.query(SocialLink).filter_by(is_visible=True).all()
    team = (
        db.query(TeamMember)
        .filter(TeamMember.is_visible == True)  # noqa: E712
        .order_by(TeamMember.display_order)
        .all()
    )
    hours = {}
    if settings and settings.opening_hours:
        try:
            hours = json.loads(settings.opening_hours)
        except Exception:
            hours = {}
    return render_template(
        "public/contact.html",
        settings=settings,
        socials=socials,
        team=team,
        hours=hours,
    )


@public_bp.route("/book-table", methods=["GET", "POST"])
def book_table():
    from app.services.reservation_service import create_reservation
    from datetime import datetime

    db = get_session()
    settings = db.query(RestaurantSettings).first()
    # Ensure reservations are on if settings row exists with null-ish
    if settings is not None and settings.reservation_enabled is None:
        settings.reservation_enabled = True
        try:
            db.commit()
        except Exception:
            db.rollback()

    if request.method == "POST":
        try:
            name = (request.form.get("customer_name") or "").strip()
            phone = (request.form.get("customer_phone") or "").strip()
            email = (request.form.get("customer_email") or "").strip()
            date_str = (request.form.get("reservation_date") or "").strip()
            time_str = (request.form.get("reservation_time") or "").strip()
            guests_raw = request.form.get("guest_count") or "2"
            area = (request.form.get("seating_area") or "").strip() or None
            requests_text = (request.form.get("special_requests") or "").strip() or None

            if not name:
                raise ValueError("Please enter your name.")
            if not phone:
                raise ValueError("Please enter your phone number.")
            if not email or "@" not in email:
                raise ValueError("Please enter a valid email.")
            if not date_str or not time_str:
                raise ValueError("Please choose date and time.")

            try:
                guests = int(guests_raw)
            except ValueError:
                guests = 2
            if guests < 1:
                guests = 1

            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Invalid date format.")
            # Accept HH:MM or HH:MM:SS
            try:
                t = datetime.strptime(time_str, "%H:%M").time()
            except ValueError:
                try:
                    t = datetime.strptime(time_str, "%H:%M:%S").time()
                except ValueError:
                    raise ValueError("Invalid time format.")

            reservation = create_reservation(
                db,
                customer_name=name,
                customer_phone=phone,
                customer_email=email,
                reservation_date=d,
                reservation_time=t,
                guest_count=guests,
                seating_area=area,
                special_requests=requests_text,
            )
            db.commit()
            try:
                from app.services.email_service import notify_reservation
                notify_reservation(reservation, settings.name if settings else "Megha Hotel")
            except Exception:
                pass
            return redirect(url_for("public.reservation_confirm", token=reservation.tracking_token))
        except ValueError as e:
            db.rollback()
            flash(str(e), "error")
        except Exception as e:
            db.rollback()
            import traceback
            traceback.print_exc()
            flash("Booking failed. Please try again or call us.", "error")

    return render_template("public/book_table.html", settings=settings)


@public_bp.route("/reservation/<token>")
def reservation_confirm(token):
    from app.models.reservation import Reservation
    db = get_session()
    reservation = db.query(Reservation).filter_by(tracking_token=token).first()
    if not reservation:
        abort(404)
    return render_template("public/reservation_status.html", reservation=reservation)




@public_bp.route("/manifest.webmanifest")
def web_manifest():
    """PWA manifest – icons from admin logo."""
    from flask import current_app
    from app.services.pwa_icons import logo_version, save_pwa_icons
    from pathlib import Path as _Path

    db = get_session()
    settings = db.query(RestaurantSettings).first()
    name = (settings.name if settings else None) or "Megha Hotel"
    short = (name[:12]) if name else "Megha Hotel"
    theme = (settings.primary_color if settings else None) or "#7B2D26"
    if theme in ("#8B4513", "#6B3410", ""):
        theme = "#7B2D26"
    bg = (settings.background_color if settings else None) or "#FAF7F2"
    if bg in ("#FFF8F0", "#FFF1E0", ""):
        bg = "#FAF7F2"

    logo = None
    if settings:
        logo = settings.favicon_url or settings.logo_url

    # Ensure icons exist on disk when logo is set
    if logo:
        try:
            save_pwa_icons(logo)
        except Exception:
            pass

    ver = logo_version(logo)
    base = (current_app.config.get("APP_URL") or request.url_root or "").rstrip("/")

    def abs_url(path: str) -> str:
        if path.startswith("http"):
            return path
        if base:
            return f"{base}{path}"
        return path

    icon_192 = abs_url(f"/pwa-icon/192.png?v={ver}")
    icon_512 = abs_url(f"/pwa-icon/512.png?v={ver}")

    manifest = {
        "name": f"{name} Restaurant",
        "short_name": short,
        "description": (settings.tagline if settings and settings.tagline else "Good Food. Great Moments."),
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "background_color": bg,
        "theme_color": theme,
        "orientation": "portrait-primary",
        "icons": [
            {"src": icon_192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": icon_192, "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": icon_512, "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": icon_512, "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    resp = jsonify(manifest)
    resp.headers["Content-Type"] = "application/manifest+json"
    resp.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    return resp


@public_bp.route("/pwa-icon/<int:size>.png")
def pwa_icon(size: int):
    """Serve PWA icon generated from current admin logo."""
    from flask import Response, send_file
    from app.services.pwa_icons import build_icon_png, save_pwa_icons
    from pathlib import Path as _Path
    import io

    if size not in (192, 512, 180, 144, 96, 48):
        size = 192

    db = get_session()
    settings = db.query(RestaurantSettings).first()
    logo = None
    if settings:
        logo = settings.favicon_url or settings.logo_url

    png = None
    if logo:
        png = build_icon_png(logo, size)
        if png:
            try:
                save_pwa_icons(logo)
            except Exception:
                pass

    if not png:
        # Fallback static icon file
        from flask import current_app as _ca
        fallback = _Path(_ca.root_path) / "static" / "icons" / f"icon-{size if size in (192, 512) else 192}.png"
        if fallback.is_file():
            return send_file(fallback, mimetype="image/png")
        # Generate plain branded fallback
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (size, size), "#7B2D26")
        d = ImageDraw.Draw(img)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()

    return Response(
        png,
        mimetype="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )




@public_bp.route("/api/time")
def api_nepali_time():
    from app.services.nepali_datetime import format_nepali_now
    return jsonify(format_nepali_now())



@public_bp.route("/riders")
def riders_page():
    """Public delivery riders page – who delivers for Megha Hotel."""
    from app.models.rider import Rider
    db = get_session()
    riders = (
        db.query(Rider)
        .filter(Rider.is_active == True)  # noqa: E712
        .order_by(Rider.full_name)
        .all()
    )
    settings = db.query(RestaurantSettings).first()
    return render_template("public/riders.html", riders=riders, settings=settings)


@public_bp.route("/api/track/<token>/delivery")
def api_track_delivery(token):
    from app.services.order_service import get_order_by_tracking
    from app.models.rider import Rider
    db = get_session()
    order = get_order_by_tracking(db, token)
    if not order:
        return jsonify({"error": "not_found"}), 404
    rider = order.rider
    ds = order.delivery_status or "pending_pickup"
    show_on_map = ds in ("picked_up", "on_the_way", "nearby", "delivered")
    return jsonify({
        "order_number": order.order_number,
        "order_type": order.order_type,
        "status": order.status,
        "delivery_status": ds,
        "delivery_address": order.delivery_address,
        "customer_lat": order.customer_lat,
        "customer_lng": order.customer_lng,
        "show_rider_on_map": show_on_map,
        "rider": None if not rider else {
            "name": rider.full_name,
            "phone": rider.phone,
            "vehicle_type": rider.vehicle_type,
            "vehicle_number": rider.vehicle_number,
            "photo_url": rider.photo_url,
            "lat": rider.last_lat if show_on_map else None,
            "lng": rider.last_lng if show_on_map else None,
            "is_available": rider.is_available,
        },
    })





@public_bp.route("/api/rider/ping", methods=["POST"])
def api_rider_ping():
    """Rider app/phone: POST {rider_id, phone, lat, lng} to update map position."""
    from app.models.rider import Rider
    from app.extensions import csrf
    from datetime import datetime, timezone
    # CSRF: allow JSON from mobile — exempt via header token optional
    data = request.get_json(silent=True) or request.form
    try:
        rider_id = int(data.get("rider_id"))
        lat = float(data.get("lat"))
        lng = float(data.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "rider_id, lat, lng required"}), 400
    phone = (data.get("phone") or "").strip()
    db = get_session()
    rider = db.get(Rider, rider_id)
    if not rider or not rider.is_active:
        return jsonify({"error": "rider not found"}), 404
    if phone and rider.phone:
        digits = lambda s: "".join(c for c in s if c.isdigit())
        if digits(phone) and digits(phone) != digits(rider.phone):
            return jsonify({"error": "phone mismatch"}), 403
    rider.last_lat = lat
    rider.last_lng = lng
    rider.last_location_at = datetime.now(timezone.utc)
    db.commit()
    return jsonify({"ok": True})



@public_bp.route("/api/delivery/estimate")
def api_delivery_estimate():
    """Estimate fee + ETA from customer lat/lng. Requires location share."""
    from app.services.delivery_service import (
        haversine_km, is_within_delivery_area,
        calculate_delivery_fee_paisa, estimate_eta_minutes,
    )
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lng required — please share your location"}), 400

    db = get_session()
    settings = db.query(RestaurantSettings).first()
    if settings and getattr(settings, "delivery_enabled", True) is False:
        return jsonify({"error": "Delivery is currently closed", "allowed": False}), 400

    center_lat = getattr(settings, "delivery_center_lat", None) if settings else None
    center_lng = getattr(settings, "delivery_center_lng", None) if settings else None
    radius = float(getattr(settings, "delivery_radius_km", 5) or 5) if settings else 5.0

    dist = None
    allowed = True
    if center_lat is not None and center_lng is not None:
        allowed, dist = is_within_delivery_area(
            lat, lng, center_lat=center_lat, center_lng=center_lng, radius_km=radius,
        )
        if dist is None:
            dist = haversine_km(center_lat, center_lng, lat, lng)
    else:
        # no hub set — no distance fee
        dist = None

    base = int(getattr(settings, "delivery_fee_paisa", 0) or 0) if settings else 0
    per_km = int(getattr(settings, "delivery_fee_per_km_paisa", 0) or 0) if settings else 0
    free_km = float(getattr(settings, "delivery_free_within_km", 0) or 0) if settings else 0
    fee = calculate_delivery_fee_paisa(dist, base_paisa=base, per_km_paisa=per_km, free_within_km=free_km)
    eta = estimate_eta_minutes(dist, vehicle_type="bike", prep_minutes=20)

    return jsonify({
        "allowed": allowed,
        "distance_km": round(dist, 2) if dist is not None else None,
        "delivery_fee_paisa": fee,
        "delivery_fee_npr": round(fee / 100, 2),
        "eta_minutes": eta,
        "radius_km": radius,
        "message": (
            None if allowed else f"Outside delivery area (max {radius} km)."
        ),
    })
