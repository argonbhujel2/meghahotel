from app.models.base import get_session
from app.models.settings import RestaurantSettings


def get_restaurant_settings() -> RestaurantSettings | None:
    """Return restaurant settings or None if DB not ready / table missing."""
    try:
        session = get_session()
        try:
            return session.query(RestaurantSettings).first()
        finally:
            try:
                session.close()
            except Exception:
                pass
    except Exception:
        return None


def format_price(paisa: int) -> str:
    npr = paisa / 100.0
    if npr == int(npr):
        return f"Rs. {int(npr)}"
    return f"Rs. {npr:.2f}"
