from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

PAYMENT_METHODS = ("cash", "qr_manual", "other")
PAYMENT_STATUSES = ("pending", "completed", "failed", "refunded")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    amount_paisa: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    transaction_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    refunded_amount_paisa: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    order = relationship("Order", back_populates="payments")

    @property
    def amount_npr(self) -> float:
        return self.amount_paisa / 100.0
