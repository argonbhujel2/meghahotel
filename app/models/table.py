from sqlalchemy import String, Boolean, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
import secrets

from app.models.base import Base, TimestampMixin


class RestaurantTable(Base, TimestampMixin):
    __tablename__ = "restaurant_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    seating_area: Mapped[str | None] = mapped_column(String(80), nullable=True)  # Indoor, Outdoor, etc.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="available", nullable=False)  # available, occupied, reserved

    qr_tokens = relationship("TableQRToken", back_populates="table", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="table")

    def __repr__(self):
        return f"<Table {self.table_number}>"


class TableQRToken(Base, TimestampMixin):
    __tablename__ = "table_qr_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(Integer, ForeignKey("restaurant_tables.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    table = relationship("RestaurantTable", back_populates="qr_tokens")

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    def get_url(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/t/{self.token}"
