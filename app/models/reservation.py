from datetime import datetime, date, time, timezone
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, Date, Time, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
import secrets

from app.models.base import Base, TimestampMixin

RESERVATION_STATUSES = (
    "pending",
    "confirmed",
    "rejected",
    "cancelled",
    "completed",
    "no_show",
)


class Reservation(Base, TimestampMixin):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    tracking_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    reservation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reservation_time: Mapped[time] = mapped_column(Time, nullable=False)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    seating_area: Mapped[str | None] = mapped_column(String(80), nullable=True)
    table_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("restaurant_tables.id"), nullable=True)
    special_requests: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    table = relationship("RestaurantTable")
    status_history = relationship("ReservationStatusHistory", back_populates="reservation", cascade="all, delete-orphan")

    @staticmethod
    def generate_reference() -> str:
        now = datetime.now(timezone.utc)
        suffix = secrets.token_hex(2).upper()
        return f"BK-{now.strftime('%Y%m%d')}-{suffix}"

    @staticmethod
    def generate_tracking_token() -> str:
        return secrets.token_urlsafe(32)

    def __repr__(self):
        return f"<Reservation {self.booking_reference}>"


class ReservationStatusHistory(Base):
    __tablename__ = "reservation_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    reservation = relationship("Reservation", back_populates="status_history")


class BlockedReservationSlot(Base, TimestampMixin):
    __tablename__ = "blocked_reservation_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    block_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)  # null = whole day
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
