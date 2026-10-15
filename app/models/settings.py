from sqlalchemy import String, Boolean, Integer, Text, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RestaurantSettings(Base, TimestampMixin):
    """Singleton-like settings row (id=1)."""
    __tablename__ = "restaurant_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), default="Megha Hotel", nullable=False)
    tagline: Mapped[str] = mapped_column(String(255), default="Good Food. Great Moments.", nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    map_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    map_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    opening_hours: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    closing_days: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "Sunday"
    about_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    hero_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hero_subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hero_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(20), default="#8B4513", nullable=False)
    accent_color: Mapped[str] = mapped_column(String(20), default="#D4A574", nullable=False)
    background_color: Mapped[str] = mapped_column(String(20), default="#FFF8F0", nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="NPR", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kathmandu", nullable=False)
    takeaway_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reservation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reservation_duration_minutes: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    reservation_slot_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    advance_booking_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    tax_rate_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    service_charge_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payment_qr_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    play_store_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    delivery_radius_km: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    delivery_center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_center_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_fee_paisa: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_fee_per_km_paisa: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_free_within_km: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    delivery_areas_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    policies: Mapped[str | None] = mapped_column(Text, nullable=True)


class WebsiteSection(Base, TimestampMixin):
    __tablename__ = "website_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Testimonial(Base, TimestampMixin):
    __tablename__ = "testimonials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class GalleryImage(Base, TimestampMixin):
    __tablename__ = "gallery_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SocialLink(Base, TimestampMixin):
    __tablename__ = "social_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # facebook, instagram, etc.
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TeamMember(Base, TimestampMixin):
    """People behind the hotel – owners, managers, etc."""
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role_title: Mapped[str] = mapped_column(String(100), nullable=False)  # Owner, Manager, Chef
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
