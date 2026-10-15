"""Order creation, validation, and status management."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.order import (
    Order, OrderItem, OrderItemAddon, OrderStatusHistory,
    OrderIdempotencyKey, ORDER_STATUSES,
)
from app.models.menu import MenuItem, MenuItemVariant, MenuAddon
from app.models.table import RestaurantTable, TableQRToken
from app.models.payment import Payment
from app.models.settings import RestaurantSettings


ALLOWED_TRANSITIONS = {
    "placed": ["accepted", "preparing", "rejected", "cancelled"],
    "accepted": ["preparing", "ready", "cancelled"],
    "preparing": ["ready", "served", "cancelled"],
    "ready": ["served", "completed", "cancelled"],
    "served": ["completed", "cancelled"],
    "completed": [],
    "rejected": [],
    "cancelled": [],
}


def allowed_next_statuses(current: str) -> list[str]:
    return list(ALLOWED_TRANSITIONS.get(current or "placed", []))



def create_order(
    session: Session,
    *,
    order_type: str,
    table_token: str | None = None,
    items: list[dict],
    special_instructions: str | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    customer_email: str | None = None,
    delivery_address: str | None = None,
    delivery_notes: str | None = None,
    delivery_fee_paisa: int = 0,
    customer_lat: float | None = None,
    customer_lng: float | None = None,
    idempotency_key: str | None = None,
) -> Order:
    """
    Create a validated order.
    items: [{"menu_item_id": int, "variant_id": int|None, "quantity": int,
             "addon_ids": [int], "special_instructions": str|None}, ...]
    """
    # Idempotency
    if idempotency_key:
        existing = session.query(OrderIdempotencyKey).filter_by(key=idempotency_key).first()
        if existing and existing.order_id:
            order = session.get(Order, existing.order_id)
            if order:
                return order

    table = None
    if order_type == "delivery":
        if not delivery_address:
            raise ValueError("Delivery address is required.")
        settings = session.query(RestaurantSettings).first()
        if settings and getattr(settings, "delivery_enabled", True) is False:
            raise ValueError("Online delivery is currently unavailable.")
        from app.services.delivery_service import is_within_delivery_area
        if settings and settings.delivery_center_lat and settings.delivery_center_lng:
            ok, dist = is_within_delivery_area(
                customer_lat, customer_lng,
                center_lat=settings.delivery_center_lat,
                center_lng=settings.delivery_center_lng,
                radius_km=getattr(settings, "delivery_radius_km", 5) or 5,
            )
            if customer_lat is None or customer_lng is None:
                raise ValueError("Please enable location so we can check if we deliver to your area.")
            if not ok:
                raise ValueError(
                    f"Sorry, you are outside our delivery area"
                    + (f" ({dist:.1f} km away, max {settings.delivery_radius_km} km)." if dist is not None else ".")
                )
        # Fee from distance (admin base + per km)
        from app.services.delivery_service import calculate_delivery_fee_paisa
        if settings:
            _, dist_for_fee = is_within_delivery_area(
                customer_lat, customer_lng,
                center_lat=settings.delivery_center_lat,
                center_lng=settings.delivery_center_lng,
                radius_km=getattr(settings, "delivery_radius_km", 5) or 5,
            ) if settings.delivery_center_lat and settings.delivery_center_lng else (True, None)
            # recompute dist if needed
            if dist_for_fee is None and customer_lat and customer_lng and settings.delivery_center_lat:
                from app.services.delivery_service import haversine_km
                dist_for_fee = haversine_km(
                    settings.delivery_center_lat, settings.delivery_center_lng,
                    customer_lat, customer_lng,
                )
            computed = calculate_delivery_fee_paisa(
                dist_for_fee,
                base_paisa=int(getattr(settings, "delivery_fee_paisa", 0) or 0),
                per_km_paisa=int(getattr(settings, "delivery_fee_per_km_paisa", 0) or 0),
                free_within_km=float(getattr(settings, "delivery_free_within_km", 0) or 0),
            )
            if not delivery_fee_paisa:
                delivery_fee_paisa = computed
    if order_type == "dine_in":
        if not table_token:
            raise ValueError("Table token is required for dine-in orders.")
        qr = (
            session.query(TableQRToken)
            .filter_by(token=table_token, is_active=True)
            .first()
        )
        if not qr:
            raise ValueError("Invalid or inactive table QR code.")
        table = session.get(RestaurantTable, qr.table_id)
        if not table or not table.is_active:
            raise ValueError("Table is not available.")

    if not items:
        raise ValueError("Order must contain at least one item.")

    settings = session.query(RestaurantSettings).first()
    tax_rate = (settings.tax_rate_percent or 0) / 100.0 if settings else 0
    service_rate = (settings.service_charge_percent or 0) / 100.0 if settings else 0

    order = Order(
        order_number=Order.generate_order_number(),
        tracking_token=Order.generate_tracking_token(),
        order_type=order_type,
        table_id=table.id if table else None,
        status="placed",
        payment_status="unpaid",
        special_instructions=special_instructions,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        delivery_address=delivery_address,
        delivery_notes=delivery_notes,
        delivery_fee_paisa=delivery_fee_paisa or 0,
        delivery_status="pending_pickup" if order_type == "delivery" else None,
        customer_lat=customer_lat,
        customer_lng=customer_lng,
    )
    session.add(order)
    session.flush()

    subtotal = 0
    for raw in items:
        menu_item = session.get(MenuItem, raw["menu_item_id"])
        if not menu_item or not menu_item.is_available:
            raise ValueError(f"Item unavailable: {raw.get('menu_item_id')}")

        variant = None
        unit_price = menu_item.effective_price_paisa
        variant_name = None
        if raw.get("variant_id"):
            variant = session.get(MenuItemVariant, raw["variant_id"])
            if not variant or variant.item_id != menu_item.id or not variant.is_available:
                raise ValueError("Invalid or unavailable variant.")
            unit_price = variant.price_paisa
            variant_name = variant.name

        qty = max(1, int(raw.get("quantity", 1)))
        line_addons_total = 0
        addon_snapshots = []

        for aid in raw.get("addon_ids") or []:
            addon = session.get(MenuAddon, aid)
            if not addon or not addon.is_active:
                continue
            line_addons_total += addon.price_paisa
            addon_snapshots.append((addon.name, addon.price_paisa))

        line_total = (unit_price + line_addons_total) * qty
        subtotal += line_total

        oi = OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            item_name=menu_item.name,
            variant_name=variant_name,
            unit_price_paisa=unit_price,
            quantity=qty,
            line_total_paisa=line_total,
            special_instructions=raw.get("special_instructions"),
        )
        session.add(oi)
        session.flush()

        for aname, aprice in addon_snapshots:
            session.add(OrderItemAddon(
                order_item_id=oi.id,
                addon_name=aname,
                price_paisa=aprice,
            ))

    tax = int(round(subtotal * tax_rate))
    service = int(round(subtotal * service_rate))
    fee = delivery_fee_paisa if order_type == "delivery" else 0
    total = subtotal + tax + service + fee

    order.subtotal_paisa = subtotal
    order.tax_paisa = tax
    order.service_charge_paisa = service
    order.total_paisa = total

    # Status history
    session.add(OrderStatusHistory(
        order_id=order.id,
        status="placed",
        note="Order placed by customer",
    ))

    if idempotency_key:
        session.add(OrderIdempotencyKey(key=idempotency_key, order_id=order.id))

    session.flush()
    return order


def update_order_status(
    session: Session,
    order: Order,
    new_status: str,
    user_id: int | None = None,
    note: str | None = None,
    prep_time_minutes: int | None = None,
    force: bool = False,
) -> Order:
    if not new_status:
        raise ValueError("Please select a status.")
    new_status = str(new_status).strip().lower()
    if new_status not in ORDER_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    if new_status == order.status:
        return order  # no-op
    allowed = ALLOWED_TRANSITIONS.get(order.status, [])
    if not force and new_status not in allowed:
        raise ValueError(
            f"Cannot change from '{order.status}' to '{new_status}'. "
            f"Allowed: {', '.join(allowed) if allowed else 'none (final status)'}."
        )

    order.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == "accepted":
        order.accepted_at = now
        if prep_time_minutes:
            order.prep_time_estimate_minutes = prep_time_minutes
    elif new_status == "ready":
        order.ready_at = now
    elif new_status == "completed":
        order.completed_at = now
    elif new_status == "rejected":
        order.rejection_reason = note
    elif new_status == "cancelled":
        order.cancellation_reason = note

    session.add(OrderStatusHistory(
        order_id=order.id,
        status=new_status,
        changed_by_id=user_id,
        note=note,
    ))
    session.flush()
    return order


def get_order_by_tracking(session: Session, token: str) -> Order | None:
    from sqlalchemy.orm import joinedload
    return (
        session.query(Order)
        .options(
            joinedload(Order.table),
            joinedload(Order.rider),
            joinedload(Order.items).joinedload(OrderItem.addons),
            joinedload(Order.status_history),
            joinedload(Order.payments),
        )
        .filter_by(tracking_token=token)
        .first()
    )
