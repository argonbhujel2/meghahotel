"""SMTP email notifications for orders, reservations, and admin alerts."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def _smtp_configured() -> bool:
    return bool(
        current_app.config.get("SMTP_HOST")
        and current_app.config.get("SMTP_USER")
        and current_app.config.get("MAIL_FROM")
    )


def send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
    if not to or not _smtp_configured():
        current_app.logger.info(f"Email skipped (not configured or no recipient): {subject} -> {to}")
        return False
    host = current_app.config["SMTP_HOST"]
    port = int(current_app.config.get("SMTP_PORT") or 587)
    user = current_app.config["SMTP_USER"]
    password = current_app.config.get("SMTP_PASSWORD") or ""
    mail_from = current_app.config["MAIL_FROM"]
    use_tls = current_app.config.get("SMTP_USE_TLS", True)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if use_tls:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(mail_from, [to], msg.as_string())
        return True
    except Exception as e:
        current_app.logger.error(f"Email send failed: {e}")
        return False


def _branded_html(title: str, body: str, restaurant_name: str = "Megha Hotel") -> str:
    return f"""
    <div style="font-family:Georgia,serif;max-width:520px;margin:0 auto;background:#FFF8F0;border:2px solid #8B4513;border-radius:8px;overflow:hidden">
      <div style="background:#8B4513;color:#fff;padding:16px 20px;text-align:center">
        <div style="font-size:20px;font-weight:bold">{restaurant_name}</div>
        <div style="font-size:12px;color:#D4A574;margin-top:4px">Good Food. Great Moments.</div>
      </div>
      <div style="padding:20px;color:#2C1810">
        <h2 style="margin:0 0 12px;font-size:18px">{title}</h2>
        {body}
      </div>
      <div style="background:#F5EDE0;padding:12px 20px;font-size:11px;color:#6B5344;text-align:center">
        Urlabari, Morang, Nepal · This is an automated message.
      </div>
    </div>
    """


def notify_order_placed(order, restaurant_name: str = "Megha Hotel"):
    """Customer confirmation + admin alert."""
    if order.customer_email:
        items_html = "".join(
            f"<li>{getattr(i, 'item_name', None) or getattr(i, 'name', 'Item')} × {i.quantity}</li>"
            for i in (order.items or [])
        )
        total = getattr(order, "total_amount", None) or getattr(order, "grand_total", "")
        track = f"/track/{order.tracking_token}"
        base = current_app.config.get("APP_URL", "")
        body = f"""
        <p>Thank you for ordering with us.</p>
        <ul>{items_html}</ul>
        <p><strong>Total: {total}</strong></p>
        <p>Status: {order.status}</p>
        <p style="margin-top:16px"><a href="{base}{track}" style="background:#8B4513;color:#fff;padding:10px 16px;text-decoration:none;border-radius:4px;display:inline-block">Track your order</a></p>
        <p style="font-size:12px;color:#6B5344;margin-top:12px">Order number: {order.order_number}</p>
        """
        html = _branded_html(f"Order confirmed – {order.order_number}", body, restaurant_name)
        send_email(order.customer_email, f"Order {order.order_number} – {restaurant_name}", html)

    # Admin alert
    admin = current_app.config.get("ADMIN_NOTIFY_EMAIL")
    if admin:
        body = f"""
        <p>New order <strong>{order.order_number}</strong></p>
        <p>Customer: {getattr(order, 'customer_name', '')} · {getattr(order, 'customer_phone', '')}</p>
        <p>Type: {getattr(order, 'order_type', '')} · Total: {getattr(order, 'total_amount', '')}</p>
        <p><a href="{current_app.config.get('APP_URL', '')}/admin/orders/{order.id}">Open in admin</a></p>
        """
        html = _branded_html(f"New order {order.order_number}", body, restaurant_name)
        send_email(admin, f"[New order] {order.order_number}", html)


def notify_order_status(order, restaurant_name: str = "Megha Hotel"):
    if not order.customer_email:
        return
    labels = {
        "accepted": "Your order has been accepted",
        "preparing": "Your food is being prepared",
        "ready": "Your order is ready",
        "served": "Your order has been served",
        "completed": "Order completed – thank you!",
        "cancelled": "Your order was cancelled",
        "rejected": "Your order could not be accepted",
        "out_for_delivery": "Your order is on the way",
        "delivered": "Your order has been delivered",
    }
    title = labels.get(order.status, f"Order update: {order.status}")
    # Also check delivery_status for delivery orders
    ds = getattr(order, "delivery_status", None)
    if ds == "out_for_delivery":
        title = "Your order is on the way"
    elif ds == "delivered":
        title = "Your order has been delivered"
    body = f"<p>Order <strong>{order.order_number}</strong> is now: <strong>{order.status}</strong>.</p>"
    if ds:
        body += f"<p>Delivery status: <strong>{ds}</strong>.</p>"
    if getattr(order, "cancellation_reason", None):
        body += f"<p>Reason: {order.cancellation_reason}</p>"
    if getattr(order, "rejection_reason", None):
        body += f"<p>Reason: {order.rejection_reason}</p>"
    base = current_app.config.get("APP_URL", "")
    body += f'<p style="margin-top:16px"><a href="{base}/track/{order.tracking_token}" style="color:#8B4513">Track order</a></p>'
    html = _branded_html(title, body, restaurant_name)
    send_email(order.customer_email, f"{title} – {order.order_number}", html)


def notify_reservation(reservation, restaurant_name: str = "Megha Hotel"):
    """Customer confirmation + admin alert on new/updated reservation."""
    if reservation.customer_email:
        status = reservation.status
        body = f"""
        <p>Status: <strong>{status}</strong></p>
        <p>Date: {reservation.reservation_date} at {reservation.reservation_time}</p>
        <p>Guests: {reservation.guest_count}</p>
        <p>Name: {reservation.customer_name}</p>
        <p>Reference: <strong>{reservation.booking_reference}</strong></p>
        """
        html = _branded_html(
            f"Reservation {reservation.booking_reference}",
            body,
            restaurant_name,
        )
        send_email(
            reservation.customer_email,
            f"Reservation {reservation.booking_reference} – {restaurant_name}",
            html,
        )

    admin = current_app.config.get("ADMIN_NOTIFY_EMAIL")
    if admin and reservation.status in ("pending", "confirmed"):
        body = f"""
        <p>Reservation <strong>{reservation.booking_reference}</strong> – {reservation.status}</p>
        <p>{reservation.customer_name} · {getattr(reservation, 'customer_phone', '')}</p>
        <p>{reservation.reservation_date} {reservation.reservation_time} · {reservation.guest_count} guests</p>
        <p><a href="{current_app.config.get('APP_URL', '')}/admin/reservations">Open reservations</a></p>
        """
        html = _branded_html(f"Reservation {reservation.booking_reference}", body, restaurant_name)
        send_email(admin, f"[Reservation] {reservation.booking_reference}", html)


def notify_rider_assigned(order, rider, restaurant_name: str = "Megha Hotel"):
    """Optional: email customer when a rider is assigned."""
    if not order.customer_email:
        return
    body = f"""
    <p>A delivery rider has been assigned to order <strong>{order.order_number}</strong>.</p>
    <p>Rider: {getattr(rider, 'full_name', 'Our rider')}</p>
    <p><a href="{current_app.config.get('APP_URL', '')}/track/{order.tracking_token}">Track live</a></p>
    """
    html = _branded_html("Rider assigned", body, restaurant_name)
    send_email(order.customer_email, f"Rider assigned – {order.order_number}", html)
