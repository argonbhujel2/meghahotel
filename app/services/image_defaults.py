"""Hardcoded default images – always shown until admin replaces with a working upload."""

DEFAULT_DISH = "/static/images/defaults/dish.jpg"
DEFAULT_CATEGORY = "/static/images/defaults/category.jpg"
DEFAULT_TEAM = "/static/images/defaults/team.jpg"
DEFAULT_LOGO = "/static/images/defaults/logo.jpg"
DEFAULT_HERO = "/static/images/defaults/hero.jpg"
DEFAULT_PAYMENT_QR = "/static/images/defaults/payment-qr.jpg"
DEFAULT_FAVICON = "/static/images/defaults/favicon.jpg"

# Per-category local defaults (always available offline)
MENU_CATEGORY_IMAGES = {
    "breakfast": "/static/images/defaults/cat-breakfast.jpg",
    "snacks": "/static/uploads/menu/snacks-cat.jpg",
    "momo": "/static/uploads/menu/momo-cat.jpg",
    "chowmein-noodles": "/static/images/defaults/cat-noodles.jpg",
    "rice-meals": "/static/images/defaults/cat-rice.jpg",
    "beverages": "/static/images/defaults/cat-drinks.jpg",
    "desserts": "/static/images/defaults/cat-dessert.jpg",
}

# Per-item local defaults (real photos where we have them)
MENU_ITEM_IMAGES = {
    "french-fries": "/static/uploads/menu/french-fries.jpg",
    "chicken-wings": "/static/uploads/menu/chicken-wings.jpg",
    "steam-momo-chicken": "/static/uploads/menu/steam-momo.jpg",
    "fry-momo-veg": "/static/uploads/menu/fry-momo.jpg",
    "jhol-momo": "/static/uploads/menu/jhol-momo.jpg",
    "egg-breakfast": "/static/images/defaults/dish-breakfast.jpg",
    "pancake-stack": "/static/images/defaults/dish-breakfast.jpg",
    "chicken-chowmein": "/static/images/defaults/dish-noodle.jpg",
    "veg-chowmein": "/static/images/defaults/dish-noodle.jpg",
    "chicken-biryani": "/static/images/defaults/dish-rice.jpg",
    "dal-bhat-tarkari": "/static/images/defaults/dish-rice.jpg",
    "masala-tea": "/static/images/defaults/dish-drink.jpg",
    "fresh-lime-soda": "/static/images/defaults/dish-drink.jpg",
    "mango-lassi": "/static/images/defaults/dish-drink.jpg",
    "gulab-jamun": "/static/images/defaults/dish-dessert.jpg",
}

# Map category slug → dish default (for items without specific image)
_CATEGORY_DISH_DEFAULT = {
    "breakfast": "/static/images/defaults/dish-breakfast.jpg",
    "snacks": "/static/images/defaults/dish-snack.jpg",
    "momo": "/static/images/defaults/dish-momo.jpg",
    "chowmein-noodles": "/static/images/defaults/dish-noodle.jpg",
    "rice-meals": "/static/images/defaults/dish-rice.jpg",
    "beverages": "/static/images/defaults/dish-drink.jpg",
    "desserts": "/static/images/defaults/dish-dessert.jpg",
}


def _is_usable(url: str | None) -> bool:
    """True only for non-empty local /static paths or cloudinary-style https we trust."""
    if not url:
        return False
    u = str(url).strip()
    if not u:
        return False
    # Broken / external free-image hosts that often fail
    bad_hosts = (
        "images.unsplash.com",
        "source.unsplash.com",
        "picsum.photos",
        "via.placeholder.com",
        "placehold.co",
        "placeholder.com",
    )
    low = u.lower()
    for h in bad_hosts:
        if h in low:
            return False
    # Local static or uploaded / cloudinary / other https
    if u.startswith("/static/") or u.startswith("https://") or u.startswith("http://"):
        return True
    return False


def img(url: str | None, kind: str = "dish", slug: str | None = None) -> str:
    """
    Image to display.
    - Uses admin URL only if it looks usable (not empty, not broken stock hosts).
    - Otherwise returns hardcoded local default.
    kind: dish | category | team | logo | hero | payment_qr | favicon
    slug: optional menu item/category slug for better default
    """
    if _is_usable(url):
        return str(url).strip()

    if kind == "category" and slug and slug in MENU_CATEGORY_IMAGES:
        return MENU_CATEGORY_IMAGES[slug]
    if kind == "dish" and slug and slug in MENU_ITEM_IMAGES:
        return MENU_ITEM_IMAGES[slug]

    mapping = {
        "dish": DEFAULT_DISH,
        "category": DEFAULT_CATEGORY,
        "team": DEFAULT_TEAM,
        "logo": DEFAULT_LOGO,
        "hero": DEFAULT_HERO,
        "payment_qr": DEFAULT_PAYMENT_QR,
        "favicon": DEFAULT_FAVICON,
    }
    return mapping.get(kind, DEFAULT_DISH)


def dish_img(item) -> str:
    """Resolve image for a MenuItem object."""
    slug = getattr(item, "slug", None)
    url = getattr(item, "image_url", None)
    if _is_usable(url):
        return str(url).strip()
    if slug and slug in MENU_ITEM_IMAGES:
        return MENU_ITEM_IMAGES[slug]
    # try category
    cat = getattr(item, "category", None)
    cat_slug = getattr(cat, "slug", None) if cat else None
    if cat_slug and cat_slug in _CATEGORY_DISH_DEFAULT:
        return _CATEGORY_DISH_DEFAULT[cat_slug]
    return DEFAULT_DISH


def category_img(cat) -> str:
    """Resolve image for a MenuCategory object."""
    slug = getattr(cat, "slug", None)
    url = getattr(cat, "image_url", None)
    if _is_usable(url):
        return str(url).strip()
    if slug and slug in MENU_CATEGORY_IMAGES:
        return MENU_CATEGORY_IMAGES[slug]
    return DEFAULT_CATEGORY
