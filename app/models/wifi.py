from sqlalchemy import String, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WifiSettings(Base, TimestampMixin):
    """Singleton-like Wi-Fi configuration (usually id=1)."""
    __tablename__ = "wifi_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ssid: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    password: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    security_type: Mapped[str] = mapped_column(String(20), default="WPA", nullable=False)  # WPA, WEP, nopass
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
