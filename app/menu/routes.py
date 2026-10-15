from flask import Blueprint, jsonify
from app.models.base import get_session
from app.models.menu import MenuCategory, MenuItem

menu_bp = Blueprint("menu", __name__)


@menu_bp.route("/api/items")
def api_items():
    db = get_session()
    items = db.query(MenuItem).filter(MenuItem.is_available == True).all()  # noqa: E712
    result = []
    for i in items:
        result.append({
            "id": i.id,
            "name": i.name,
            "slug": i.slug,
            "short_description": i.short_description,
            "price_paisa": i.effective_price_paisa,
            "image_url": i.image_url,
            "category_id": i.category_id,
            "prep_time_minutes": i.prep_time_minutes,
            "variants": [
                {"id": v.id, "name": v.name, "price_paisa": v.price_paisa, "is_default": v.is_default}
                for v in i.variants if v.is_available
            ],
            "addons": [
                {"id": la.addon.id, "name": la.addon.name, "price_paisa": la.addon.price_paisa}
                for la in i.item_addons if la.addon and la.addon.is_active
            ],
        })
    return jsonify(result)


@menu_bp.route("/api/categories")
def api_categories():
    db = get_session()
    cats = (
        db.query(MenuCategory)
        .filter(MenuCategory.is_active == True)  # noqa: E712
        .order_by(MenuCategory.display_order)
        .all()
    )
    return jsonify([{"id": c.id, "name": c.name, "slug": c.slug} for c in cats])
