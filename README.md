# Megha Hotel – Restaurant Management System

Production-ready restaurant website and management platform for **Megha Hotel**, Urlabari, Morang, Nepal.

**Tagline:** Good Food. Great Moments.

## Features

- Premium public restaurant website (mobile-first + installable PWA)
- Dynamic digital menu with categories, prices, featured dishes
- Table-specific QR code ordering (dine-in)
- Shopping cart and order submission with server-side validation
- Live order tracking (polling)
- Table reservation system with availability checks
- Kitchen display system
- Wi-Fi QR code generator
- Full admin dashboard (menu, tables, orders, reservations, settings, staff, reports)
- Role-based access (Super Admin, Manager, Cashier, Kitchen, Waiter)
- **Rider portal** – separate login at `/rider/login`, installable as mobile app (PWA)
- Cash / manual QR payment recording
- Sales and menu reports with CSV export
- **Turso (libSQL)** database + local SQLite fallback
- **Cloudinary** image uploads
- **Email notifications** for orders, status changes, reservations, admin alerts

## Tech Stack

- **Frontend:** HTML5, CSS3, vanilla JavaScript, PWA (manifest + service worker)
- **Backend:** Python Flask
- **Database:** Turso (libSQL) via SQLAlchemy + sqlalchemy-libsql (or local SQLite)
- **Images:** Cloudinary (required on Vercel)
- **Auth:** Flask-Login + Werkzeug password hashing
- **Email:** SMTP (Gmail App Password recommended)
- **Hosting:** Vercel (or any Gunicorn host)

---

## Quick Start (Local Development)

```bash
cd megha-hotel
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Leave TURSO_* empty or set USE_LOCAL_DB=1 – app uses megha_hotel.db

export FLASK_APP=wsgi.py
export USE_LOCAL_DB=1
flask init-db            # creates tables + seeds sample menu, tables, admin
flask run                # http://localhost:5000
```

### Default admin login

- **Email:** `admin@meghahotel.com`
- **Password:** `Admin@12345`

Change this password immediately in production.

### Rider login

- Create riders in Admin → Riders
- Riders sign in at **`/rider/login`**
- On phone: open `/rider/login` → “Add to Home Screen” for app-like experience

---

## Production: Turso + Cloudinary + Email + Vercel

### 1. Turso database

```bash
# Install CLI: https://docs.turso.tech/cli
turso db create megha-hotel
turso db show megha-hotel --url          # → TURSO_DATABASE_URL
turso db tokens create megha-hotel       # → TURSO_AUTH_TOKEN
```

### 2. Cloudinary

1. Sign up at [cloudinary.com](https://cloudinary.com)
2. Dashboard → copy **Cloud name**, **API Key**, **API Secret**
3. Images upload to folder `megha-hotel/...` and return HTTPS URLs

### 3. Email (Gmail example)

1. Google Account → Security → 2-Step Verification → App passwords
2. Create app password → use as `SMTP_PASSWORD`
3. Set `SMTP_USER` to your Gmail address
4. Optional: `ADMIN_NOTIFY_EMAIL` for new-order / reservation alerts

### 4. Deploy on Vercel

```bash
# Install Vercel CLI
npm i -g vercel

cd megha-hotel
vercel
```

**Environment variables** (Vercel Dashboard → Project → Settings → Environment Variables):

| Variable | Example |
|----------|---------|
| `SECRET_KEY` | long random string |
| `FLASK_ENV` | `production` |
| `TURSO_DATABASE_URL` | `libsql://xxx.turso.io` |
| `TURSO_AUTH_TOKEN` | token |
| `CLOUDINARY_CLOUD_NAME` | your cloud name |
| `CLOUDINARY_API_KEY` | key |
| `CLOUDINARY_API_SECRET` | secret |
| `APP_URL` | `https://your-app.vercel.app` |
| `SESSION_COOKIE_SECURE` | `1` |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `you@gmail.com` |
| `SMTP_PASSWORD` | app password |
| `SMTP_USE_TLS` | `1` |
| `MAIL_FROM` | `Megha Hotel <noreply@…>` |
| `ADMIN_NOTIFY_EMAIL` | `admin@meghahotel.com` |

After first deploy, initialize the database once (local machine with same env vars):

```bash
export FLASK_APP=wsgi.py
# export all TURSO_* and other vars
flask init-db
flask create-admin
```

Or use a one-off Vercel serverless call / Turso SQL shell to run migrations if preferred.

**Note:** Vercel serverless has ephemeral filesystem. Always use **Cloudinary** for uploads and **Turso** for the database. Do not set `USE_LOCAL_DB=1` on Vercel.

### Alternative hosts

```bash
# Railway / Render / any VPS
gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app
```

---

## Main URLs

| URL | Description |
|-----|-------------|
| `/` | Public homepage (PWA) |
| `/menu` | Digital menu |
| `/t/<token>` | Table QR entry → menu bound to table |
| `/cart` | Cart & place order |
| `/track/<token>` | Order tracking |
| `/book` | Table reservation |
| `/admin` | Admin dashboard |
| `/kitchen` | Kitchen display |
| **`/rider/login`** | **Rider app login (installable PWA)** |
| `/rider/dashboard` | Rider active deliveries |

---

## Email events

| Event | Recipient |
|-------|-----------|
| Order placed | Customer + Admin (`ADMIN_NOTIFY_EMAIL`) |
| Order status change | Customer |
| Rider assigned | Customer |
| Reservation created / status updated | Customer + Admin (on pending/confirmed) |

---

## Rider PWA (mobile app-like)

1. Open `https://your-domain/rider/login` on the rider’s phone
2. **iOS Safari:** Share → Add to Home Screen  
3. **Android Chrome:** Menu → Install app / Add to Home screen  
4. App opens full-screen with its own icon, theme color, and offline shell

Scope is `/rider/` only so it does not conflict with the main restaurant PWA.
