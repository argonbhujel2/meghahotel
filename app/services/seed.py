"""Seed default roles, admin user, settings, sample menu, and tables."""
import json
from sqlalchemy.orm import Session

from app.models.user import User, Role
from app.models.settings import RestaurantSettings, WebsiteSection, Testimonial
from app.models.menu import MenuCategory, MenuItem
from app.models.table import RestaurantTable, TableQRToken
from app.models.wifi import WifiSettings
from app.models.settings import TeamMember


DEFAULT_ROLES = [
    ("super_admin", "Full system access", '["*"]'),
    ("manager", "Orders, reservations, menu, tables, reports", '["orders","reservations","menu","tables","reports","content"]'),
    ("cashier", "Billing and payment operations", '["orders","payments"]'),
    ("kitchen", "Kitchen orders and preparation statuses", '["kitchen","orders.view","orders.status"]'),
    ("waiter", "Table service and order status", '["orders.view","orders.status","tables"]'),
]

SAMPLE_CATEGORIES = [
    ("Breakfast", "breakfast", 1),
    ("Snacks", "snacks", 2),
    ("Momo", "momo", 3),
    ("Chowmein & Noodles", "chowmein-noodles", 4),
    ("Rice & Meals", "rice-meals", 5),
    ("Beverages", "beverages", 6),
    ("Desserts", "desserts", 7),
]

SAMPLE_ITEMS = [
    # (category_slug, name, slug, short_desc, price_npr, featured, popular)
    ("breakfast", "Egg Breakfast", "egg-breakfast", "Two eggs with toast and tea", 250, True, True),
    ("breakfast", "Pancake Stack", "pancake-stack", "Fluffy pancakes with honey", 320, False, True),
    ("snacks", "French Fries", "french-fries", "Crispy golden fries", 180, False, True),
    ("snacks", "Chicken Wings", "chicken-wings", "Spicy fried chicken wings", 350, True, False),
    ("momo", "Steam Momo (Chicken)", "steam-momo-chicken", "10 pcs steamed chicken momo", 220, True, True),
    ("momo", "Fry Momo (Veg)", "fry-momo-veg", "10 pcs fried vegetable momo", 200, False, True),
    ("momo", "Jhol Momo", "jhol-momo", "Momo in spicy soup", 250, True, True),
    ("chowmein-noodles", "Chicken Chowmein", "chicken-chowmein", "Stir-fried noodles with chicken", 280, True, True),
    ("chowmein-noodles", "Veg Chowmein", "veg-chowmein", "Stir-fried noodles with vegetables", 220, False, False),
    ("rice-meals", "Chicken Biryani", "chicken-biryani", "Aromatic rice with chicken", 450, True, True),
    ("rice-meals", "Dal Bhat Tarkari", "dal-bhat-tarkari", "Traditional Nepali thali", 300, True, True),
    ("beverages", "Masala Tea", "masala-tea", "Spiced Nepali tea", 50, False, True),
    ("beverages", "Fresh Lime Soda", "fresh-lime-soda", "Refreshing lime soda", 80, False, False),
    ("beverages", "Mango Lassi", "mango-lassi", "Sweet mango yogurt drink", 120, True, True),
    ("desserts", "Gulab Jamun", "gulab-jamun", "2 pcs sweet milk dumplings", 100, False, True),
]


def seed_defaults(session: Session) -> None:
    # Roles
    existing_roles = {r.name for r in session.query(Role).all()}
    for name, desc, perms in DEFAULT_ROLES:
        if name not in existing_roles:
            session.add(Role(name=name, description=desc, permissions=perms))
    session.flush()

    # Super admin if none exists
    if session.query(User).count() == 0:
        admin = User(
            email="admin@meghahotel.com",
            full_name="System Administrator",
            is_active=True,
        )
        admin.set_password("Admin@12345")
        super_role = session.query(Role).filter_by(name="super_admin").first()
        if super_role:
            admin.roles.append(super_role)
        session.add(admin)

    # Restaurant settings
    if session.query(RestaurantSettings).count() == 0:
        settings = RestaurantSettings(
            name="Megha Hotel",
            tagline="Good Food. Great Moments.",
            phone="",
            whatsapp="",
            email="info@meghahotel.com",
            address="Urlabari, Morang, Nepal",
            about_text=(
                "Welcome to Megha Hotel Restaurant in Urlabari, Morang. "
                "We serve authentic Nepali, Indian and Continental dishes "
                "in a warm and welcoming atmosphere. Good Food. Great Moments."
            ),
            hero_title="Good Food. Great Moments.",
            hero_subtitle="Authentic flavors from the heart of Urlabari, Morang",
            opening_hours=json.dumps({
                "monday": {"open": "08:00", "close": "21:00"},
                "tuesday": {"open": "08:00", "close": "21:00"},
                "wednesday": {"open": "08:00", "close": "21:00"},
                "thursday": {"open": "08:00", "close": "21:00"},
                "friday": {"open": "08:00", "close": "22:00"},
                "saturday": {"open": "08:00", "close": "22:00"},
                "sunday": {"open": "09:00", "close": "21:00"},
            }),
            seo_title="Megha Hotel Restaurant | Urlabari, Morang – Good Food. Great Moments.",
            seo_description=(
                "Dine at Megha Hotel Restaurant in Urlabari, Morang, Nepal. "
                "Enjoy momo, chowmein, biryani, and more. Book a table or order via QR."
            ),
            primary_color="#7B2D26",
            accent_color="#C4A35A",
            background_color="#FAF7F2",
        )
        session.add(settings)

    # Website sections
    if session.query(WebsiteSection).count() == 0:
        sections = [
            ("hero", "Hero", 1),
            ("featured", "Featured Dishes", 2),
            ("categories", "Categories", 3),
            ("story", "Our Story", 4),
            ("gallery", "Gallery", 5),
            ("testimonials", "Testimonials", 6),
            ("hours", "Opening Hours", 7),
            ("contact", "Contact", 8),
        ]
        for key, title, order in sections:
            session.add(WebsiteSection(key=key, title=title, is_visible=True, display_order=order))

    # Sample testimonials
    if session.query(Testimonial).count() == 0:
        session.add(Testimonial(
            customer_name="Ramesh K.",
            content="Best momo in Urlabari! The jhol momo is outstanding.",
            rating=5,
            display_order=1,
        ))
        session.add(Testimonial(
            customer_name="Sita T.",
            content="Clean place, friendly staff, and delicious Dal Bhat. Highly recommend.",
            rating=5,
            display_order=2,
        ))
        session.add(Testimonial(
            customer_name="Anil S.",
            content="Great value and authentic flavors. Perfect for family dinners.",
            rating=4,
            display_order=3,
        ))

    # Menu categories & items
    if session.query(MenuCategory).count() == 0:
        cat_map = {}
        from app.services.image_defaults import MENU_CATEGORY_IMAGES, MENU_ITEM_IMAGES, DEFAULT_CATEGORY, DEFAULT_DISH
        cat_images = dict(MENU_CATEGORY_IMAGES)
        item_images = dict(MENU_ITEM_IMAGES)
        for name, slug, order in SAMPLE_CATEGORIES:
            cat = MenuCategory(
                name=name, slug=slug, is_active=True, display_order=order,
                image_url=cat_images.get(slug),
            )
            session.add(cat)
            session.flush()
            cat_map[slug] = cat.id

        for cat_slug, name, slug, short, price, featured, popular in SAMPLE_ITEMS:
            session.add(MenuItem(
                category_id=cat_map[cat_slug],
                name=name,
                slug=slug,
                short_description=short,
                price_paisa=int(price * 100),
                is_available=True,
                is_featured=featured,
                is_popular=popular,
                prep_time_minutes=15,
                image_url=item_images.get(slug),
            ))

    # Sample tables
    if session.query(RestaurantTable).count() == 0:
        for i in range(1, 11):
            t = RestaurantTable(
                table_number=str(i),
                name=f"Table {i}",
                capacity=4 if i <= 6 else 6,
                seating_area="Indoor" if i <= 8 else "Outdoor",
                is_active=True,
            )
            session.add(t)
            session.flush()
            token = TableQRToken(
                table_id=t.id,
                token=TableQRToken.generate_token(),
                is_active=True,
            )
            session.add(token)


    # Backfill category / item images if empty (safe for existing DBs)
    # Force local images for every category & item (no external URLs)
    from app.services.image_defaults import (
        MENU_CATEGORY_IMAGES, MENU_ITEM_IMAGES,
        DEFAULT_DISH, DEFAULT_CATEGORY, DEFAULT_LOGO, DEFAULT_HERO, DEFAULT_FAVICON,
    )
    for cat in session.query(MenuCategory).all():
        # Always prefer local default map; overwrite broken external URLs
        local = MENU_CATEGORY_IMAGES.get(cat.slug, DEFAULT_CATEGORY)
        if not cat.image_url or "unsplash" in (cat.image_url or "") or "placeholder" in (cat.image_url or ""):
            cat.image_url = local
        elif not cat.image_url.startswith("/static/") and not cat.image_url.startswith("https://res.cloudinary"):
            cat.image_url = local
    for item in session.query(MenuItem).all():
        local = MENU_ITEM_IMAGES.get(item.slug, DEFAULT_DISH)
        if not item.image_url or "unsplash" in (item.image_url or "") or "placeholder" in (item.image_url or ""):
            item.image_url = local
        elif not item.image_url.startswith("/static/") and not item.image_url.startswith("https://res.cloudinary"):
            item.image_url = local

    # Wi-Fi settings placeholder
    if session.query(WifiSettings).count() == 0:
        session.add(WifiSettings(
            ssid="MeghaHotel-Guest",
            password="",
            security_type="WPA",
            instructions="Scan the QR code to connect to Megha Hotel Wi-Fi.",
            is_active=True,
        ))


    # Backfill theme colors + default images (until admin replaces)
    from app.services.image_defaults import DEFAULT_LOGO, DEFAULT_HERO, DEFAULT_FAVICON
    s = session.query(RestaurantSettings).first()
    if s:
        if not s.primary_color or s.primary_color in ("#8B4513", "#6B3410"):
            s.primary_color = "#7B2D26"
        if not s.accent_color or s.accent_color in ("#D4A574", "#E8C9A0"):
            s.accent_color = "#C4A35A"
        if not s.background_color or s.background_color in ("#FFF8F0", "#FFF1E0"):
            s.background_color = "#FAF7F2"
        if s.reservation_enabled is None:
            s.reservation_enabled = True
        # Always keep working local defaults until admin uploads Cloudinary/local
        if not s.logo_url or "unsplash" in (s.logo_url or ""):
            s.logo_url = DEFAULT_LOGO
        if not s.hero_image_url or "unsplash" in (s.hero_image_url or ""):
            s.hero_image_url = DEFAULT_HERO
        if hasattr(s, "favicon_url") and (not s.favicon_url or "unsplash" in (s.favicon_url or "")):
            s.favicon_url = DEFAULT_FAVICON

    # Team / owners – empty placeholders; admin fills real details
    if session.query(TeamMember).count() == 0:
        session.add(TeamMember(
            full_name="Owner Name",
            role_title="Owner",
            bio="Welcome to Megha Hotel. Please update this profile in the admin panel.",
            is_visible=False,
            display_order=1,
        ))
