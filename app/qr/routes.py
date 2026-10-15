from flask import Blueprint

qr_bp = Blueprint("qr", __name__)
# Table QR entry is under public_bp (/t/<token>); admin QR under admin_bp.
