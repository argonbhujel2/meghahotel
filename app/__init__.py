"""Megha Hotel Restaurant Management System – Flask application factory."""
import os
from flask import Flask, render_template
from app.config import config_by_name, Config
from app.extensions import login_manager, csrf


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        instance_relative_config=True,
    )
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Extensions
    csrf.init_app(app)
    login_manager.init_app(app)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        from app.models.base import remove_session
        remove_session()

    from app.models.user import User
    from app.models.base import get_session

    @login_manager.user_loader
    def load_user(user_id):
        """Load user for Flask-Login. Keep in request-scoped session (do not close/expunge)."""
        from sqlalchemy.orm import joinedload
        try:
            session = get_session()
            user = (
                session.query(User)
                .options(joinedload(User.roles))
                .filter(User.id == int(user_id))
                .first()
            )
            if user:
                # Cache role names for templates / permission checks
                try:
                    user._role_names_cache = [r.name for r in (user.roles or [])]
                except Exception:
                    user._role_names_cache = []
            return user
        except Exception:
            return None

    # Register blueprints
    from app.site.routes import public_bp
    from app.rider.routes import rider_bp
    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.menu.routes import menu_bp
    from app.orders.routes import orders_bp
    from app.reservations.routes import reservations_bp
    from app.qr.routes import qr_bp
    from app.kitchen.routes import kitchen_bp
    from app.reports.routes import reports_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(rider_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(menu_bp, url_prefix="/menu")
    app.register_blueprint(orders_bp, url_prefix="/orders")
    app.register_blueprint(reservations_bp, url_prefix="/reservations")
    app.register_blueprint(qr_bp)
    app.register_blueprint(kitchen_bp, url_prefix="/kitchen")
    app.register_blueprint(reports_bp, url_prefix="/admin/reports")

    # JSON rider location pings from phones (no CSRF)
    try:
        from app.site.routes import api_rider_ping
        csrf.exempt(api_rider_ping)
    except Exception:
        pass


    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    # Context processors
    @app.context_processor
    def inject_globals():
        from app.services.settings_service import get_restaurant_settings
        from app.services.image_defaults import (
            img as default_img,
            dish_img,
            category_img,
            DEFAULT_DISH,
            DEFAULT_LOGO,
            DEFAULT_HERO,
            DEFAULT_FAVICON,
            DEFAULT_TEAM,
        )
        settings = get_restaurant_settings()
        logo = default_img(settings.logo_url if settings else None, "logo")
        hero = default_img(settings.hero_image_url if settings else None, "hero")
        favicon = default_img(
            (settings.favicon_url if settings and getattr(settings, "favicon_url", None) else None)
            or (settings.logo_url if settings else None),
            "favicon",
        )
        return {
            "restaurant": settings,
            "app_name": settings.name if settings else "Megha Hotel",
            "currency_symbol": "Rs.",
            "default_img": default_img,
            "dish_img": dish_img,
            "category_img": category_img,
            "DEFAULT_DISH": DEFAULT_DISH,
            "DEFAULT_TEAM": DEFAULT_TEAM,
            "restaurant_logo": logo,
            "restaurant_hero": hero,
            "restaurant_favicon": favicon,
        }

    # CLI commands
    @app.cli.command("init-db")
    def init_db_command():
        """Initialize the database and seed defaults."""
        from app.models.base import init_db
        init_db(app)
        print("Database initialized and seeded.")

    @app.cli.command("create-admin")
    def create_admin_command():
        """Create or reset the super admin user."""
        from app.models.base import get_session
        from app.models.user import User, Role
        session = get_session()
        try:
            admin = session.query(User).filter_by(email="admin@meghahotel.com").first()
            if not admin:
                admin = User(email="admin@meghahotel.com", full_name="System Administrator", is_active=True)
                session.add(admin)
            admin.set_password("Admin@12345")
            role = session.query(Role).filter_by(name="super_admin").first()
            if role and role not in admin.roles:
                admin.roles.append(role)
            session.commit()
            print("Admin ready: admin@meghahotel.com / Admin@12345")
        finally:
            session.close()

    # Optional DB init (local only; on Vercel/Turso run flask init-db once)
    if os.environ.get("USE_LOCAL_DB") == "1" or os.environ.get("INIT_DB_ON_START") == "1":
        with app.app_context():
            try:
                from app.models.base import init_db
                init_db(app)
            except Exception as e:
                app.logger.warning(f"DB init on startup: {e}")

    return app
