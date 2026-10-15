from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, Table, Text, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permissions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of permissions

    users = relationship("User", secondary=user_roles, back_populates="roles")

    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    roles = relationship("Role", secondary=user_roles, back_populates="users")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, *role_names: str) -> bool:
        names = getattr(self, "_role_names_cache", None)
        if names is None:
            try:
                names = [r.name for r in (self.roles or [])]
                self._role_names_cache = names
            except Exception:
                names = []
        return any(n in names for n in role_names)

    
    def has_permission(self, permission: str) -> bool:
        if self.has_role("super_admin"):
            return True
        try:
            for role in self.roles:
                if role.permissions and permission in role.permissions:
                    return True
        except Exception:
            pass
        return False

    @property
    def role_names(self) -> list[str]:
        names = getattr(self, "_role_names_cache", None)
        if names is not None:
            return names
        try:
            return [r.name for r in self.roles]
        except Exception:
            return []

    def __repr__(self):
        return f"<User {self.email}>"
