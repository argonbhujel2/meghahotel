"""Database base and engine configuration for Turso / local SQLite."""
import os
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, scoped_session
from sqlalchemy import DateTime

from app.config import Config


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


_engine = None
_SessionLocal = None


def get_database_url():
    """Build the correct database URL for Turso or local SQLite."""
    if Config.USE_LOCAL_DB:
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "megha_hotel.db",
        )
        return f"sqlite:///{db_path}"

    url = Config.TURSO_DATABASE_URL
    token = Config.TURSO_AUTH_TOKEN

    if not url or not token:
        raise RuntimeError(
            "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set, "
            "or set USE_LOCAL_DB=1 for local development."
        )

    if url.startswith("libsql://"):
        host = url.replace("libsql://", "")
        return f"sqlite+libsql://{host}?secure=true"
    if url.startswith("https://"):
        host = url.replace("https://", "")
        return f"sqlite+libsql://{host}?secure=true"
    return f"sqlite+libsql://{url}?secure=true"


def get_engine(echo=False):
    global _engine
    if _engine is not None:
        return _engine

    url = get_database_url()
    connect_args = {"check_same_thread": False}

    if not Config.USE_LOCAL_DB:
        connect_args["auth_token"] = Config.TURSO_AUTH_TOKEN

    _engine = create_engine(
        url,
        connect_args=connect_args,
        echo=echo,
        pool_pre_ping=True,
    )

    if Config.USE_LOCAL_DB or "libsql" in url or "sqlite" in url:

        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            except Exception:
                pass
            cursor.close()

    return _engine


def get_session_factory():
    """Thread/request-local scoped session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = scoped_session(
            sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
        )
    return _SessionLocal


def get_session():
    """Return the current request-scoped session. Do NOT close it in views —
    it is removed automatically on app context teardown."""
    return get_session_factory()


def remove_session():
    """Remove the scoped session (call on request teardown)."""
    factory = get_session_factory()
    factory.remove()


@contextmanager
def session_scope():
    """Transactional scope for scripts / one-off work."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(app=None):
    """Create all tables and seed essential data."""
    from app.models import (  # noqa: F401
        User, Role, RestaurantSettings, MenuCategory, MenuItem,
        RestaurantTable, Order, Reservation, WifiSettings,
        WebsiteSection, Announcement, Testimonial, GalleryImage,
        SocialLink, TeamMember, Payment, AuditLog, MenuItemVariant, MenuAddon,
        MenuItemAddon, TableQRToken, OrderItem, OrderItemAddon,
        OrderStatusHistory, OrderIdempotencyKey, ReservationStatusHistory,
        BlockedReservationSlot,
        Rider,
    )

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    # SQLite column add for existing DBs
    try:
        from sqlalchemy import text as sa_text
        with engine.connect() as conn:
            cols = [r[1] for r in conn.execute(sa_text("PRAGMA table_info(restaurant_settings)")).fetchall()]
            if cols and "play_store_url" not in cols:
                conn.execute(sa_text("ALTER TABLE restaurant_settings ADD COLUMN play_store_url VARCHAR(500)"))
                conn.commit()
            for col, sql in [
                ("delivery_enabled", "ALTER TABLE restaurant_settings ADD COLUMN delivery_enabled BOOLEAN DEFAULT 1"),
                ("delivery_radius_km", "ALTER TABLE restaurant_settings ADD COLUMN delivery_radius_km FLOAT DEFAULT 5"),
                ("delivery_center_lat", "ALTER TABLE restaurant_settings ADD COLUMN delivery_center_lat FLOAT"),
                ("delivery_center_lng", "ALTER TABLE restaurant_settings ADD COLUMN delivery_center_lng FLOAT"),
                ("delivery_fee_paisa", "ALTER TABLE restaurant_settings ADD COLUMN delivery_fee_paisa INTEGER DEFAULT 0"),
                ("delivery_fee_per_km_paisa", "ALTER TABLE restaurant_settings ADD COLUMN delivery_fee_per_km_paisa INTEGER DEFAULT 0"),
                ("delivery_free_within_km", "ALTER TABLE restaurant_settings ADD COLUMN delivery_free_within_km FLOAT DEFAULT 0"),
                ("delivery_areas_text", "ALTER TABLE restaurant_settings ADD COLUMN delivery_areas_text TEXT"),
            ]:
                if cols and col not in cols:
                    try:
                        conn.execute(sa_text(sql))
                        conn.commit()
                    except Exception:
                        pass
            # users 2FA columns
            ucols = [r[1] for r in conn.execute(sa_text("PRAGMA table_info(users)")).fetchall()]
            if ucols and "totp_secret" not in ucols:
                conn.execute(sa_text("ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64)"))
                conn.commit()
            if ucols and "totp_enabled" not in ucols:
                conn.execute(sa_text("ALTER TABLE users ADD COLUMN totp_enabled BOOLEAN DEFAULT 0"))
                conn.commit()
            # Order delivery columns
            ocols = [r[1] for r in conn.execute(sa_text("PRAGMA table_info(orders)")).fetchall()]
            for col, sql in [
                ("delivery_address", "ALTER TABLE orders ADD COLUMN delivery_address TEXT"),
                ("delivery_notes", "ALTER TABLE orders ADD COLUMN delivery_notes TEXT"),
                ("delivery_fee_paisa", "ALTER TABLE orders ADD COLUMN delivery_fee_paisa INTEGER DEFAULT 0"),
                ("rider_id", "ALTER TABLE orders ADD COLUMN rider_id INTEGER"),
                ("delivery_status", "ALTER TABLE orders ADD COLUMN delivery_status VARCHAR(30)"),
                ("customer_lat", "ALTER TABLE orders ADD COLUMN customer_lat FLOAT"),
                ("customer_lng", "ALTER TABLE orders ADD COLUMN customer_lng FLOAT"),
            ]:
                if ocols and col not in ocols:
                    try:
                        conn.execute(sa_text(sql))
                        conn.commit()
                    except Exception:
                        pass
        rcols = []
        try:
            rcols = [r[1] for r in conn.execute(sa_text("PRAGMA table_info(riders)")).fetchall()]
        except Exception:
            pass
        for col, sql in [
            ("username", "ALTER TABLE riders ADD COLUMN username VARCHAR(80)"),
            ("password_hash", "ALTER TABLE riders ADD COLUMN password_hash VARCHAR(255)"),
        ]:
            if rcols and col not in rcols:
                try:
                    conn.execute(sa_text(sql))
                    conn.commit()
                except Exception:
                    pass
    except Exception:
        pass

    session = get_session_factory()()
    try:
        from app.services.seed import seed_defaults
        seed_defaults(session)
        session.commit()
    except Exception as e:
        session.rollback()
        if app:
            app.logger.warning(f"Seed skipped or partial: {e}")
        else:
            print(f"Seed warning: {e}")
    finally:
        session.close()
        get_session_factory().remove()
