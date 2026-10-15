from datetime import datetime, timezone
from sqlalchemy import Float,  String, Boolean, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
import secrets

from app.models.base import Base, TimestampMixin

ORDER_STATUSES = (
    "placed",
    "accepted",
    "preparing",
    "ready",
    "served",
    "completed",
    "rejected",
    "cancelled",
)

PAYMENT_STATUSES = ("unpaid", "partially_paid", "paid", "refunded", "partially_refunded")

ORDER_TYPES = ("dine_in", "takeaway", "delivery")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    tracking_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    order_type: Mapped[str] = mapped_column(String(20), default="dine_in", nullable=False)
    table_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("restaurant_tables.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="placed", nullable=False, index=True)
    payment_status: Mapped[str] = mapped_column(String(30), default="unpaid", nullable=False)
    # Money in paisa
    subtotal_paisa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_paisa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_paisa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    service_charge_paisa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_paisa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Delivery
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_fee_paisa: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rider_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("riders.id"), nullable=True, index=True)
    delivery_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    customer_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    customer_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    # pending_pickup | picked_up | on_the_way | nearby | delivered
    prep_time_estimate_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rider = relationship("Rider", back_populates="orders")
    table = relationship("RestaurantTable", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_history = relationship("OrderStatusHistory", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")

    @staticmethod
    def generate_order_number() -> str:
        # Format: MH-YYYYMMDD-XXXX
        now = datetime.now(timezone.utc)
        suffix = secrets.token_hex(2).upper()
        return f"MH-{now.strftime('%Y%m%d')}-{suffix}"

    @staticmethod
    def generate_tracking_token() -> str:
        return secrets.token_urlsafe(32)

    @property
    def total_npr(self) -> float:
        return self.total_paisa / 100.0

    def __repr__(self):
        return f"<Order {self.order_number}>"


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    menu_item_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("menu_items.id"), nullable=True)
    # Snapshot fields – preserved even if menu item changes
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    variant_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit_price_paisa: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    line_total_paisa: Mapped[int] = mapped_column(Integer, nullable=False)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    order = relationship("Order", back_populates="items")
    addons = relationship("OrderItemAddon", back_populates="order_item", cascade="all, delete-orphan")


class OrderItemAddon(Base):
    __tablename__ = "order_item_addons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False)
    addon_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_paisa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    order_item = relationship("OrderItem", back_populates="addons")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    order = relationship("Order", back_populates="status_history")


class OrderIdempotencyKey(Base):
    """Prevents duplicate order submissions."""
    __tablename__ = "order_idempotency_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
