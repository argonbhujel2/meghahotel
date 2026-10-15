"""Generate and serve PWA icons from admin logo."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from urllib.request import urlopen

from flask import current_app
from PIL import Image


def _resolve_logo_image(logo_url: str) -> Image.Image | None:
    if not logo_url:
        return None
    try:
        if logo_url.startswith("http://") or logo_url.startswith("https://"):
            with urlopen(logo_url, timeout=10) as resp:
                return Image.open(io.BytesIO(resp.read())).convert("RGBA")

        # Local static path
        rel = logo_url
        if rel.startswith("/static/"):
            rel = rel[len("/static/") :]
        elif rel.startswith("static/"):
            rel = rel[len("static/") :]

        candidates = [
            Path(current_app.root_path) / "static" / rel,
            Path(current_app.static_folder or "") / rel,
            Path(current_app.root_path) / logo_url.lstrip("/"),
        ]
        for path in candidates:
            if path and path.is_file():
                return Image.open(path).convert("RGBA")
    except Exception as e:
        current_app.logger.warning("PWA logo load failed: %s", e)
    return None


def build_icon_png(logo_url: str, size: int = 192) -> bytes | None:
    """Return PNG bytes for a square PWA icon with logo centered."""
    src = _resolve_logo_image(logo_url)
    if src is None:
        return None

    # Cream background matching site
    canvas = Image.new("RGBA", (size, size), (250, 247, 242, 255))
    pad = max(int(size * 0.1), 8)
    inner = size - pad * 2
    logo = src.copy()
    logo.thumbnail((inner, inner), Image.Resampling.LANCZOS)
    x = (size - logo.width) // 2
    y = (size - logo.height) // 2
    if logo.mode == "RGBA":
        canvas.paste(logo, (x, y), logo)
    else:
        canvas.paste(logo.convert("RGBA"), (x, y))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def save_pwa_icons(logo_url: str) -> dict:
    """Write icon-192.png and icon-512.png under static/uploads/pwa and static/icons."""
    results = {}
    root = Path(current_app.root_path)
    dirs = [
        root / "static" / "uploads" / "pwa",
        root / "static" / "icons",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    for size in (192, 512):
        data = build_icon_png(logo_url, size)
        if not data:
            continue
        name = f"icon-{size}.png"
        for d in dirs:
            (d / name).write_bytes(data)
        results[str(size)] = f"/static/uploads/pwa/{name}"
    return results


def logo_version(logo_url: str | None) -> str:
    if not logo_url:
        return "0"
    return hashlib.md5(logo_url.encode("utf-8")).hexdigest()[:10]
