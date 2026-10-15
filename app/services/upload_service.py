"""Image upload: local static/uploads with optional Cloudinary."""
import os
import uuid
from pathlib import Path
from flask import current_app

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _upload_dir(subdir: str) -> Path:
    root = Path(current_app.root_path) / "static" / "uploads" / subdir
    root.mkdir(parents=True, exist_ok=True)
    return root


def upload_image(file_storage, subdir: str = "misc") -> str | None:
    """
    Save uploaded file. Returns a public URL path starting with /static/...
    """
    if not file_storage or not getattr(file_storage, "filename", None):
        return None
    filename = file_storage.filename
    if not allowed_file(filename):
        raise ValueError("Only PNG, JPG, JPEG, GIF, WEBP images are allowed.")

    # size check
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_SIZE:
        raise ValueError("Image must be under 5 MB.")
    if size == 0:
        raise ValueError("Empty file.")

    # Cloudinary optional
    cloud = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    key = current_app.config.get("CLOUDINARY_API_KEY")
    secret = current_app.config.get("CLOUDINARY_API_SECRET")
    if cloud and key and secret:
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(cloud_name=cloud, api_key=key, api_secret=secret)
            result = cloudinary.uploader.upload(
                file_storage,
                folder=f"megha-hotel/{subdir}",
                resource_type="image",
            )
            return result.get("secure_url")
        except Exception:
            file_storage.stream.seek(0)

    ext = filename.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    dest_dir = _upload_dir(subdir)
    dest = dest_dir / name
    file_storage.save(str(dest))

    if not dest.is_file() or dest.stat().st_size == 0:
        raise ValueError("Failed to save image.")

    # Public path Flask serves from app/static
    return f"/static/uploads/{subdir}/{name}"


def generate_pwa_icons_from_logo(logo_path_or_url: str) -> dict:
    """Build 192/512 PWA icons from restaurant logo (saved to disk)."""
    from app.services.pwa_icons import save_pwa_icons
    if not logo_path_or_url:
        return {}
    return save_pwa_icons(logo_path_or_url)
