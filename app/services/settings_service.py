from functools import lru_cache
from app.models.base import get_session
from app.models.settings import RestaurantSettings


def get_restaurant_settings() -> RestaurantSettings | None:
    session = get_session()
    try:
        return session.query(RestaurantSettings).first()
    finally:
        session.close()


def format_price(paisa: int) -> str:
    npr = paisa / 100.0
    if npr == int(npr):
        return f"Rs. {int(npr)}"
    return f"Rs. {npr:.2f}"
