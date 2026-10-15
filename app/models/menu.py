from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MenuCategory(Base, TimestampMixin):
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    items = relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MenuCategory {self.name}>"


class MenuItem(Base, TimestampMixin):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("menu_categories.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    short_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Prices stored in minor units (paisa) to avoid float issues; 1 NPR = 100 paisa
    price_paisa: Mapped[int] = mapped_column(Integer, nullable=False)
    discounted_price_paisa: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_popular: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dietary_labels: Mapped[str | None] = mapped_column(String(255), nullable=True)  # comma-separated
    allergens: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    category = relationship("MenuCategory", back_populates="items")
    variants = relationship("MenuItemVariant", back_populates="item", cascade="all, delete-orphan")
    item_addons = relationship("MenuItemAddon", back_populates="item", cascade="all, delete-orphan")

    @property
    def price_npr(self) -> float:
        return self.price_paisa / 100.0

    @property
    def discounted_price_npr(self) -> float | None:
        if self.discounted_price_paisa is not None:
            return self.discounted_price_paisa / 100.0
        return None

    @property
    def effective_price_paisa(self) -> int:
        if self.discounted_price_paisa is not None and self.discounted_price_paisa < self.price_paisa:
            return self.discounted_price_paisa
        return self.price_paisa

    def __repr__(self):
        return f"<MenuItem {self.name}>"


class MenuItemVariant(Base, TimestampMixin):
    __tablename__ = "menu_item_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)  # e.g. Small, Large
    price_paisa: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    item = relationship("MenuItem", back_populates="variants")


class MenuAddon(Base, TimestampMixin):
    """Global add-on definition (e.g. Extra Cheese)."""
    __tablename__ = "menu_addons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_paisa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    item_links = relationship("MenuItemAddon", back_populates="addon")


class MenuItemAddon(Base):
    """Link table: which add-ons are available for which items."""
    __tablename__ = "menu_item_addons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    addon_id: Mapped[int] = mapped_column(Integer, ForeignKey("menu_addons.id", ondelete="CASCADE"), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    item = relationship("MenuItem", back_populates="item_addons")
    addon = relationship("MenuAddon", back_populates="item_links")
