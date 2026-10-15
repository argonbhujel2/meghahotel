"""Reservation booking – keep simple and reliable."""
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session

from app.models.reservation import Reservation, ReservationStatusHistory
from app.models.table import RestaurantTable
from app.models.settings import RestaurantSettings

try:
    import pytz
    KTM = pytz.timezone("Asia/Kathmandu")
except Exception:
    KTM = None


def _today() -> date:
    if KTM:
        return datetime.now(KTM).date()
    return datetime.now().date()


def create_reservation(
    session: Session,
    *,
    customer_name: str,
    customer_phone: str,
    customer_email: str | None,
    reservation_date: date,
    reservation_time: time,
    guest_count: int,
    seating_area: str | None = None,
    preferred_table_id: int | None = None,
    special_requests: str | None = None,
) -> Reservation:
    if not customer_name or not customer_phone:
        raise ValueError("Name and phone are required.")
    if guest_count < 1:
        raise ValueError("Please enter number of guests.")

    settings = session.query(RestaurantSettings).first()
    if settings is not None and settings.reservation_enabled is False:
        raise ValueError("Online reservations are closed. Please call the restaurant.")

    today = _today()
    if reservation_date < today:
        raise ValueError("Cannot book a past date. Please choose today or a future date.")

    max_days = 30
    if settings and getattr(settings, "advance_booking_days", None):
        max_days = settings.advance_booking_days or 30
    if reservation_date > today + timedelta(days=max_days):
        raise ValueError(f"Please choose a date within the next {max_days} days.")

    # Optional table assignment – never block booking
    table_id = None
    try:
        tables = (
            session.query(RestaurantTable)
            .filter(RestaurantTable.is_active == True)  # noqa: E712
            .order_by(RestaurantTable.capacity)
            .all()
        )
        if preferred_table_id:
            for t in tables:
                if t.id == preferred_table_id:
                    table_id = t.id
                    break
        if table_id is None and tables:
            for t in tables:
                if t.capacity >= guest_count:
                    table_id = t.id
                    break
            if table_id is None:
                table_id = tables[0].id
    except Exception:
        table_id = None

    reservation = Reservation(
        booking_reference=Reservation.generate_reference(),
        tracking_token=Reservation.generate_tracking_token(),
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        customer_email=(customer_email or "").strip() or None,
        reservation_date=reservation_date,
        reservation_time=reservation_time,
        guest_count=guest_count,
        seating_area=seating_area or None,
        table_id=table_id,
        special_requests=special_requests or None,
        status="pending",
    )
    session.add(reservation)
    session.flush()
    try:
        session.add(ReservationStatusHistory(
            reservation_id=reservation.id,
            status="pending",
            note="Requested online",
        ))
        session.flush()
    except Exception:
        pass
    return reservation
