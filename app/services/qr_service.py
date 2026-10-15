"""Decorative branded QR codes for tables, Wi-Fi, and general use."""
import io
from pathlib import Path
from urllib.request import urlopen

import qrcode
from qrcode.constants import ERROR_CORRECT_H
from flask import current_app
from PIL import Image, ImageDraw, ImageFont

from app.models.wifi import WifiSettings

# Warm restaurant palette
BG = (255, 248, 240)       # cream
FRAME = (139, 69, 19)      # brown
ACCENT = (212, 165, 116)   # gold
TEXT = (44, 24, 16)        # dark brown
WHITE = (255, 255, 255)


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _load_logo(logo_url: str | None, size: int) -> Image.Image | None:
    if not logo_url:
        return None
    try:
        if logo_url.startswith("/static/"):
            path = Path(current_app.root_path) / logo_url.lstrip("/")
            if not path.is_file():
                path = Path(current_app.root_path) / "static" / logo_url.split("/static/")[-1]
            if path.is_file():
                img = Image.open(path).convert("RGBA")
            else:
                return None
        elif logo_url.startswith("http"):
            with urlopen(logo_url, timeout=5) as resp:
                img = Image.open(io.BytesIO(resp.read())).convert("RGBA")
        else:
            path = Path(current_app.root_path) / "static" / logo_url
            if path.is_file():
                img = Image.open(path).convert("RGBA")
            else:
                return None
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        # Round-ish white backing
        canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        # center logo
        x = (size - img.width) // 2
        y = (size - img.height) // 2
        canvas.paste(img, (x, y), img if img.mode == "RGBA" else None)
        return canvas
    except Exception:
        return None


def generate_qr_image(
    data: str,
    *,
    title: str = "Megha Hotel",
    subtitle: str = "",
    footer: str = "Good Food. Great Moments.",
    logo_url: str | None = None,
    box_size: int = 8,
) -> bytes:
    """Branded QR PNG with frame, title, optional logo in centre."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=box_size,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=FRAME, back_color=WHITE).convert("RGBA")

    # Optional logo in QR centre
    logo = _load_logo(logo_url, max(qr_img.width // 5, 48))
    if logo:
        # white pad under logo
        pad = 8
        lw, lh = logo.size
        plate = Image.new("RGBA", (lw + pad * 2, lh + pad * 2), WHITE + (255,))
        plate.paste(logo, (pad, pad), logo)
        pos = ((qr_img.width - plate.width) // 2, (qr_img.height - plate.height) // 2)
        qr_img.paste(plate, pos, plate)

    # Layout sizes
    pad_x = 40
    header_h = 90 if subtitle else 70
    footer_h = 50
    qr_side = qr_img.width
    width = max(qr_side + pad_x * 2, 360)
    height = header_h + qr_side + footer_h + 40

    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)

    # Outer frame
    draw.rectangle([4, 4, width - 5, height - 5], outline=FRAME, width=3)
    draw.rectangle([10, 10, width - 11, height - 11], outline=ACCENT, width=2)

    # Header bar
    draw.rectangle([14, 14, width - 15, header_h + 8], fill=FRAME)
    font_title = _font(22, bold=True)
    font_sub = _font(14)
    font_foot = _font(12)

    # Title centred
    tw = draw.textlength(title, font=font_title) if hasattr(draw, "textlength") else len(title) * 12
    draw.text(((width - tw) / 2, 28), title, fill=WHITE, font=font_title)
    if subtitle:
        sw = draw.textlength(subtitle, font=font_sub) if hasattr(draw, "textlength") else len(subtitle) * 8
        draw.text(((width - sw) / 2, 56), subtitle, fill=ACCENT, font=font_sub)

    # QR centred
    qx = (width - qr_side) // 2
    qy = header_h + 16
    # soft white plate behind QR
    draw.rounded_rectangle(
        [qx - 8, qy - 8, qx + qr_side + 8, qy + qr_side + 8],
        radius=8,
        fill=WHITE,
        outline=ACCENT,
        width=2,
    )
    canvas.paste(qr_img, (qx, qy), qr_img)

    # Footer
    fy = qy + qr_side + 20
    fw = draw.textlength(footer, font=font_foot) if hasattr(draw, "textlength") else len(footer) * 7
    draw.text(((width - fw) / 2, fy), footer, fill=TEXT, font=font_foot)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def table_qr_url(token: str) -> str:
    base = current_app.config.get("APP_URL", "http://localhost:5000")
    return f"{base.rstrip('/')}/t/{token}"


def wifi_qr_payload(settings: WifiSettings) -> str:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")

    t = settings.security_type or "WPA"
    s = esc(settings.ssid or "")
    p = esc(settings.password or "")
    h = "true" if settings.is_hidden else "false"
    return f"WIFI:T:{t};S:{s};P:{p};H:{h};;"


def get_branding():
    """Restaurant name, tagline, logo from settings."""
    try:
        from app.models.base import get_session
        from app.models.settings import RestaurantSettings
        db = get_session()
        s = db.query(RestaurantSettings).first()
        if s:
            return {
                "name": s.name or "Megha Hotel",
                "tagline": s.tagline or "Good Food. Great Moments.",
                "logo_url": s.logo_url,
            }
    except Exception:
        pass
    return {"name": "Megha Hotel", "tagline": "Good Food. Great Moments.", "logo_url": None}
