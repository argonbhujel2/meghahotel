"""WSGI entry for Gunicorn / Vercel fallback."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app

config_name = os.environ.get("FLASK_ENV", "production")
app = create_app(config_name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
